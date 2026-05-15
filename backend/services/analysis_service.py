import json
import logging
import threading

from sqlmodel import Session, select

from models.analysis_output import OUTPUT_TYPES, AnalysisOutput
from models.chunk import Chunk
from models.document import Document
from models.model_provider import ModelProvider, mask_api_key
from models.topic import Topic
from services.llm_client import LLMClientError, LLMMessage, OpenAICompatibleLLMClient
from services.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

PARTIAL_INSTRUCTION = (
    "\n\n## Batch Analysis Mode\n"
    "You are analyzing ONLY a portion (batch) of the full novel. "
    "Extract information ONLY from the provided text below. "
    "Do NOT claim this is a complete analysis of the entire novel. "
    "Be thorough for this batch — include every character, event, "
    "relationship, or theme present in these excerpts. "
    "ALWAYS include source_chunk_ids and evidence_quotes for every claim."
)

DEEPEN_INSTRUCTION = (
    "\n\n## Deepen Mode\n"
    "You previously produced the following analysis for the SAME text:\n"
    "{previous_analysis}\n\n"
    "Now re-read the excerpts and find any additional {output_type} you may have missed. "
    "Pay special attention to minor/secondary entities, background details, and early mentions. "
    "Merge your new findings with the previous analysis and output ONE complete result "
    "matching the original schema exactly. Do NOT remove items from the previous analysis — "
    "only add missing ones and correct any errors."
)

MERGE_INSTRUCTION = (
    "\n\n## Merge Mode\n"
    "You are merging multiple partial analysis results into one final output. "
    "Follow these rules:\n"
    "1. Merge duplicate characters/events/relationships that refer to the same entity.\n"
    "2. Combine evidence_quotes from all partial results.\n"
    "3. Combine source_chunk_ids from all partial results (deduplicate).\n"
    "4. Do NOT fabricate information not present in the partial results.\n"
    "5. If partial results disagree, note the tension but don't invent resolution.\n"
    "6. Output valid JSON matching the original schema exactly."
)

MAX_MERGE_INPUTS = 12  # max partial results per merge level

_TOPIC_ANALYSIS_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def acquire_topic_analysis_lock(topic_id: str) -> bool:
    """Try to acquire the per-topic analysis lock. Returns True if acquired."""
    with _LOCKS_GUARD:
        if topic_id not in _TOPIC_ANALYSIS_LOCKS:
            _TOPIC_ANALYSIS_LOCKS[topic_id] = threading.Lock()
        lock = _TOPIC_ANALYSIS_LOCKS[topic_id]
    return lock.acquire(blocking=False)


def release_topic_analysis_lock(topic_id: str) -> None:
    """Release the per-topic analysis lock."""
    with _LOCKS_GUARD:
        lock = _TOPIC_ANALYSIS_LOCKS.get(topic_id)
    if lock is not None and lock.locked():
        lock.release()


def _select_provider(topic: Topic, session: Session) -> ModelProvider:
    if topic.provider_id:
        provider = session.get(ModelProvider, topic.provider_id)
        if provider is not None:
            return provider
    provider = session.exec(
        select(ModelProvider).where(ModelProvider.is_default == True)  # noqa: E712
    ).first()
    if provider is None:
        raise ValueError("No provider configured")
    return provider


def _build_context(topic_id: str, limit_chunks: int, session: Session) -> str:
    chunks = session.exec(
        select(Chunk)
        .where(Chunk.topic_id == topic_id)
        .order_by(Chunk.chapter_index, Chunk.chunk_index)
        .limit(limit_chunks)
    ).all()
    lines = []
    for c in chunks:
        lines.append(f"[chunk_id={c.id} chapter={c.chapter_index} chunk={c.chunk_index}]\n{c.text}")
    return "\n\n".join(lines)


def _chunk_ids_from_context(topic_id: str, limit_chunks: int, session: Session) -> list[str]:
    chunks = session.exec(
        select(Chunk)
        .where(Chunk.topic_id == topic_id)
        .order_by(Chunk.chapter_index, Chunk.chunk_index)
        .limit(limit_chunks)
    ).all()
    return [c.id for c in chunks]


def _load_ordered_chunks(topic_id: str, session: Session) -> list[Chunk]:
    return list(
        session.exec(
            select(Chunk)
            .where(Chunk.topic_id == topic_id)
            .order_by(Chunk.chapter_index, Chunk.chunk_index)
        ).all()
    )


def _batch_chunks(chunks: list[Chunk], max_chars: int = 12000) -> list[list[Chunk]]:
    batches: list[list[Chunk]] = []
    current: list[Chunk] = []
    current_chars = 0
    for c in chunks:
        c_len = len(c.text)
        if current and current_chars + c_len > max_chars:
            batches.append(current)
            current = []
            current_chars = 0
        current.append(c)
        current_chars += c_len
    if current:
        batches.append(current)
    return batches


def _build_context_from_chunks(chunks: list[Chunk]) -> str:
    lines = []
    for c in chunks:
        lines.append(f"[chunk_id={c.id} chapter={c.chapter_index} chunk={c.chunk_index}]\n{c.text}")
    return "\n\n".join(lines)


def _collect_chunk_ids(chunks: list[Chunk]) -> list[str]:
    return [c.id for c in chunks]


def _run_partial_analysis(
    output_type: str,
    batch_chunks: list[Chunk],
    client: OpenAICompatibleLLMClient,
    provider: ModelProvider,
) -> dict:
    prompt = load_prompt(output_type)
    full_prompt = prompt + PARTIAL_INSTRUCTION

    context = _build_context_from_chunks(batch_chunks)

    system_msg = LLMMessage(role="system", content=full_prompt)
    user_msg = LLMMessage(
        role="user",
        content=f"Analyze the following novel excerpts (batch):\n\n{context}",
    )

    response = client.chat(
        messages=[system_msg, user_msg],
        model=provider.model_name,
        temperature=provider.temperature,
        max_tokens=provider.max_output_tokens,
        response_format={"type": "json_object"},
    )

    try:
        parsed = json.loads(response.content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in partial analysis for {output_type}: {e}") from e

    # Attach chunk ids to partial result
    parsed["_partial_chunk_ids"] = _collect_chunk_ids(batch_chunks)
    return parsed


def _merge_partial_results(
    output_type: str,
    partial_results: list[dict],
    client: OpenAICompatibleLLMClient,
    provider: ModelProvider,
) -> dict:
    if len(partial_results) == 1:
        result = partial_results[0]
        result.pop("_partial_chunk_ids", None)
        return result

    # Multi-level merge for large result sets
    while len(partial_results) > 1:
        next_level = []
        for i in range(0, len(partial_results), MAX_MERGE_INPUTS):
            batch = partial_results[i : i + MAX_MERGE_INPUTS]  # noqa: E203
            if len(batch) == 1:
                next_level.append(batch[0])
            else:
                merged = _merge_single_level(output_type, batch, client, provider)
                next_level.append(merged)
        partial_results = next_level

    result = partial_results[0]
    result.pop("_partial_chunk_ids", None)
    return result


def _merge_single_level(
    output_type: str,
    partials: list[dict],
    client: OpenAICompatibleLLMClient,
    provider: ModelProvider,
) -> dict:
    prompt = load_prompt(output_type)
    full_prompt = prompt + MERGE_INSTRUCTION

    # Build a compact representation of partial results
    parts_text_parts = []
    for i, pr in enumerate(partials):
        pr_clean = {k: v for k, v in pr.items() if k != "_partial_chunk_ids"}
        parts_text_parts.append(
            f"Partial result {i + 1}:\n{json.dumps(pr_clean, ensure_ascii=False, indent=2)}"
        )
    parts_text = "\n\n".join(parts_text_parts)

    system_msg = LLMMessage(role="system", content=full_prompt)
    user_msg = LLMMessage(
        role="user",
        content=f"Merge the following partial analysis results:\n\n{parts_text}",
    )

    response = client.chat(
        messages=[system_msg, user_msg],
        model=provider.model_name,
        temperature=provider.temperature,
        max_tokens=provider.max_output_tokens,
        response_format={"type": "json_object"},
    )

    try:
        merged = json.loads(response.content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in merge for {output_type}: {e}") from e

    # Preserve chunk ids from all partials
    all_ids = []
    for pr in partials:
        all_ids.extend(pr.get("_partial_chunk_ids", []))
    merged["_partial_chunk_ids"] = list(dict.fromkeys(all_ids))  # deduplicate, keep order

    return merged


def _delete_output_by_type(topic_id: str, output_type: str, session: Session) -> None:
    old = session.exec(
        select(AnalysisOutput).where(
            AnalysisOutput.topic_id == topic_id,
            AnalysisOutput.output_type == output_type,
        )
    ).all()
    for o in old:
        session.delete(o)
    if old:
        session.flush()


def run_single_analysis_output(
    topic_id: str,
    output_type: str,
    session: Session,
    provider_id: str | None = None,
    limit_chunks: int = 5,
    max_batch_chars: int = 12000,
) -> AnalysisOutput:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise ValueError("Topic not found")

    doc = session.exec(select(Document).where(Document.topic_id == topic_id)).first()
    if doc is None:
        raise ValueError("No document uploaded")

    if provider_id:
        provider = session.get(ModelProvider, provider_id)
        if provider is None:
            raise ValueError("Provider not found")
    else:
        provider = _select_provider(topic, session)

    client = OpenAICompatibleLLMClient(
        base_url=provider.base_url,
        api_key=provider.api_key,
    )

    all_chunks = _load_ordered_chunks(topic_id, session)
    if not all_chunks:
        raise ValueError("Document not parsed")

    batches = _batch_chunks(all_chunks, max_chars=max_batch_chars)

    if len(batches) <= 1 and len(all_chunks) <= limit_chunks:
        # Small text: single call without batch/merge overhead
        context = _build_context_from_chunks(all_chunks)
        all_chunk_ids = _collect_chunk_ids(all_chunks)

        prompt = load_prompt(output_type)
        system_msg = LLMMessage(role="system", content=prompt)
        user_msg = LLMMessage(
            role="user",
            content=f"Analyze the following novel excerpts:\n\n{context}",
        )

        try:
            response = client.chat(
                messages=[system_msg, user_msg],
                model=provider.model_name,
                temperature=provider.temperature,
                max_tokens=provider.max_output_tokens,
                response_format={"type": "json_object"},
            )
        except LLMClientError as e:
            safe = e.message.replace(provider.api_key, mask_api_key(provider.api_key))
            raise ValueError(f"LLM error for {output_type}: {safe}") from e

        try:
            parsed = json.loads(response.content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response for {output_type}") from e
    else:
        # Full batch-map-merge pipeline
        partial_results = []
        for batch in batches:
            result = _run_partial_analysis(output_type, batch, client, provider)
            partial_results.append(result)

        parsed = _merge_partial_results(output_type, partial_results, client, provider)

        # Collect all chunk ids from all batches
        all_chunk_ids = []
        for pr in partial_results:
            all_chunk_ids.extend(pr.get("_partial_chunk_ids", []))
        all_chunk_ids = list(dict.fromkeys(all_chunk_ids))

    evidence_quotes = _extract_evidence(parsed)
    source_ids = _extract_source_ids(parsed, all_chunk_ids)
    confidence = _extract_confidence(parsed)

    title_map = {
        "overview": parsed.get("title", "Work Overview"),
        "characters": f"Characters ({len(parsed.get('characters', []))} found)",
        "relations": f"Relationships ({len(parsed.get('relationships', []))} found)",
        "events": f"Events ({len(parsed.get('events', []))} found)",
        "causality": f"Causal Chains ({len(parsed.get('causal_chains', []))} found)",
        "themes": f"Themes ({len(parsed.get('themes', []))} found)",
    }

    _delete_output_by_type(topic_id, output_type, session)

    output = AnalysisOutput(
        topic_id=topic_id,
        output_type=output_type,
        title=title_map.get(output_type, output_type),
        content_json=json.dumps(parsed, ensure_ascii=False),
        source_chunk_ids=json.dumps(source_ids),
        evidence_quotes=json.dumps(evidence_quotes, ensure_ascii=False),
        confidence=confidence,
    )
    session.add(output)
    session.commit()
    session.refresh(output)
    return output


def run_structured_analysis(
    topic_id: str,
    session: Session,
    provider_id: str | None = None,
    limit_chunks: int = 5,
    output_types: list[str] | None = None,
) -> list[AnalysisOutput]:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise ValueError("Topic not found")

    doc = session.exec(select(Document).where(Document.topic_id == topic_id)).first()
    if doc is None:
        raise ValueError("No document uploaded")

    chunk = session.exec(select(Chunk).where(Chunk.topic_id == topic_id).limit(1)).first()
    if chunk is None:
        raise ValueError("Document not parsed")

    if provider_id:
        provider = session.get(ModelProvider, provider_id)
        if provider is None:
            raise ValueError("Provider not found")
    else:
        provider = _select_provider(topic, session)

    types_to_run = output_types if output_types else list(OUTPUT_TYPES)
    context = _build_context(topic_id, limit_chunks, session)
    all_chunk_ids = _chunk_ids_from_context(topic_id, limit_chunks, session)

    client = OpenAICompatibleLLMClient(
        base_url=provider.base_url,
        api_key=provider.api_key,
    )

    results = []
    for output_type in types_to_run:
        try:
            prompt = load_prompt(output_type)
        except (ValueError, FileNotFoundError) as e:
            logger.error("Failed to load prompt for %s: %s", output_type, e)
            continue

        system_msg = LLMMessage(role="system", content=prompt)
        user_msg = LLMMessage(
            role="user",
            content=f"Analyze the following novel excerpts:\n\n{context}",
        )

        try:
            response = client.chat(
                messages=[system_msg, user_msg],
                model=provider.model_name,
                temperature=provider.temperature,
                max_tokens=provider.max_output_tokens,
                response_format={"type": "json_object"},
            )
        except LLMClientError as e:
            logger.error(
                "LLM call failed for %s: %s",
                output_type,
                e.message.replace(provider.api_key, mask_api_key(provider.api_key)),
            )
            continue

        try:
            parsed = json.loads(response.content)
        except json.JSONDecodeError:
            logger.error("Invalid JSON from LLM for %s", output_type)
            continue

        evidence_quotes = _extract_evidence(parsed)
        source_ids = _extract_source_ids(parsed, all_chunk_ids)
        confidence = _extract_confidence(parsed)

        usage = response.usage or {}
        prompt_tok = usage.get("prompt_tokens", 0)
        completion_tok = usage.get("completion_tokens", 0)

        title_map = {
            "overview": parsed.get("title", "Work Overview"),
            "characters": f"Characters ({len(parsed.get('characters', []))} found)",
            "relations": f"Relationships ({len(parsed.get('relationships', []))} found)",
            "events": f"Events ({len(parsed.get('events', []))} found)",
            "causality": f"Causal Chains ({len(parsed.get('causal_chains', []))} found)",
            "themes": f"Themes ({len(parsed.get('themes', []))} found)",
        }

        output = AnalysisOutput(
            topic_id=topic_id,
            output_type=output_type,
            title=title_map.get(output_type, output_type),
            content_json=json.dumps(parsed, ensure_ascii=False),
            source_chunk_ids=json.dumps(source_ids),
            evidence_quotes=json.dumps(evidence_quotes, ensure_ascii=False),
            confidence=confidence,
            prompt_tokens=prompt_tok,
            completion_tokens=completion_tok,
        )
        session.add(output)
        session.commit()
        session.refresh(output)
        results.append(output)

    return results


def run_single_output_type(
    topic_id: str,
    output_type: str,
    session: Session,
    limit_chunks: int = 5,
    deepen: bool = False,
) -> AnalysisOutput:
    """Run analysis for a single output_type. If deepen=True, include previous output as context."""
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise ValueError("Topic not found")

    doc = session.exec(select(Document).where(Document.topic_id == topic_id)).first()
    if doc is None:
        raise ValueError("No document uploaded")

    chunk = session.exec(select(Chunk).where(Chunk.topic_id == topic_id).limit(1)).first()
    if chunk is None:
        raise ValueError("Document not parsed")

    provider = _select_provider(topic, session)

    context = _build_context(topic_id, limit_chunks, session)
    all_chunk_ids = _chunk_ids_from_context(topic_id, limit_chunks, session)

    client = OpenAICompatibleLLMClient(
        base_url=provider.base_url,
        api_key=provider.api_key,
    )

    prompt = load_prompt(output_type)

    if deepen:
        existing = session.exec(
            select(AnalysisOutput).where(
                AnalysisOutput.topic_id == topic_id,
                AnalysisOutput.output_type == output_type,
            )
        ).first()
        if existing:
            try:
                prev_json = json.loads(existing.content_json)
                prev_str = json.dumps(prev_json, ensure_ascii=False, indent=2)
            except (json.JSONDecodeError, TypeError):
                prev_str = existing.content_json
            deepen_prompt = DEEPEN_INSTRUCTION.format(
                previous_analysis=prev_str, output_type=output_type
            )
            prompt = prompt + deepen_prompt

    system_msg = LLMMessage(role="system", content=prompt)
    user_msg = LLMMessage(
        role="user",
        content=f"Analyze the following novel excerpts:\n\n{context}",
    )

    try:
        response = client.chat(
            messages=[system_msg, user_msg],
            model=provider.model_name,
            temperature=provider.temperature,
            max_tokens=provider.max_output_tokens,
            response_format={"type": "json_object"},
        )
    except LLMClientError as e:
        safe = e.message.replace(provider.api_key, mask_api_key(provider.api_key))
        raise ValueError(f"LLM error for {output_type}: {safe}") from e

    try:
        parsed = json.loads(response.content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON response for {output_type}") from e

    usage = response.usage or {}
    prompt_tok = usage.get("prompt_tokens", 0)
    completion_tok = usage.get("completion_tokens", 0)

    evidence_quotes = _extract_evidence(parsed)
    source_ids = _extract_source_ids(parsed, all_chunk_ids)
    confidence = _extract_confidence(parsed)

    title_map = {
        "overview": parsed.get("title", "Work Overview"),
        "characters": f"Characters ({len(parsed.get('characters', []))} found)",
        "relations": f"Relationships ({len(parsed.get('relationships', []))} found)",
        "events": f"Events ({len(parsed.get('events', []))} found)",
        "causality": f"Causal Chains ({len(parsed.get('causal_chains', []))} found)",
        "themes": f"Themes ({len(parsed.get('themes', []))} found)",
    }

    _delete_output_by_type(topic_id, output_type, session)

    output = AnalysisOutput(
        topic_id=topic_id,
        output_type=output_type,
        title=title_map.get(output_type, output_type),
        content_json=json.dumps(parsed, ensure_ascii=False),
        source_chunk_ids=json.dumps(source_ids),
        evidence_quotes=json.dumps(evidence_quotes, ensure_ascii=False),
        confidence=confidence,
        prompt_tokens=prompt_tok,
        completion_tokens=completion_tok,
    )
    session.add(output)
    session.commit()
    session.refresh(output)
    return output


def get_analysis_outputs(
    topic_id: str, session: Session, output_type: str | None = None
) -> list[AnalysisOutput]:
    stmt = select(AnalysisOutput).where(AnalysisOutput.topic_id == topic_id)
    if output_type:
        stmt = stmt.where(AnalysisOutput.output_type == output_type)
    return list(
        session.exec(stmt.order_by(AnalysisOutput.output_type, AnalysisOutput.created_at)).all()
    )


def delete_analysis_outputs(topic_id: str, session: Session) -> int:
    outputs = session.exec(select(AnalysisOutput).where(AnalysisOutput.topic_id == topic_id)).all()
    count = len(outputs)
    for o in outputs:
        session.delete(o)
    session.commit()
    return count


def _extract_evidence(parsed: dict) -> list[str]:
    for key in ("evidence_quotes",):
        if key in parsed and isinstance(parsed[key], list):
            return parsed[key]
    nested = parsed.get("results", parsed)
    if isinstance(nested, dict):
        evidence = nested.get("evidence_quotes", [])
        if isinstance(evidence, list):
            return evidence
    if isinstance(nested, list):
        all_evidence = []
        for item in nested:
            if isinstance(item, dict) and "evidence_quotes" in item:
                all_evidence.extend(item["evidence_quotes"])
        return all_evidence
    return []


def _extract_source_ids(parsed: dict, fallback: list[str]) -> list[str]:
    ids = parsed.get("source_chunk_ids", [])
    if isinstance(ids, list) and ids:
        return ids
    nested = parsed.get("results", parsed)
    if isinstance(nested, dict):
        ids = nested.get("source_chunk_ids", [])
        if isinstance(ids, list) and ids:
            return ids
    if isinstance(nested, list):
        all_ids = []
        for item in nested:
            if isinstance(item, dict) and "source_chunk_ids" in item:
                all_ids.extend(item["source_chunk_ids"])
        return all_ids if all_ids else fallback
    return fallback


def _extract_confidence(parsed: dict) -> float:
    confidence = parsed.get("confidence", 0.0)
    if isinstance(confidence, (int, float)):
        return float(confidence)
    nested = parsed.get("results", parsed)
    if isinstance(nested, dict):
        confidence = nested.get("confidence", 0.0)
        if isinstance(confidence, (int, float)):
            return float(confidence)
    if isinstance(nested, list):
        confidences = [
            item["confidence"] for item in nested if isinstance(item, dict) and "confidence" in item
        ]
        if confidences:
            return sum(confidences) / len(confidences)
    return 0.0
