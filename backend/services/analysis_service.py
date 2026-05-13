import json
import logging

from sqlmodel import Session, select

from models.analysis_output import OUTPUT_TYPES, AnalysisOutput
from models.chunk import Chunk
from models.document import Document
from models.model_provider import ModelProvider, mask_api_key
from models.topic import Topic
from services.llm_client import LLMClientError, LLMMessage, OpenAICompatibleLLMClient
from services.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


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
        )
        session.add(output)
        results.append(output)

    session.commit()
    return results


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
