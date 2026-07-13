"""AnalysisRun retry and explicit resume execution."""

from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from models.analysis_run import AnalysisRun
from models.enums import JobStatus
from models.local_extraction import LocalExtraction
from services import atom_normalizer, local_extraction_worker
from services.analysis_run_execution_service import (
    load_chapter_titles_by_chunk_id,
    resolve_api_key,
    serialize_attempts,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def classify_error(error: str, status_code: int | None = None) -> str:
    if status_code and status_code not in (429, 500, 502, 503, 504):
        pass
    error_lower = error.lower()
    if "json" in error_lower and "parse" in error_lower:
        return "json_parse_error"
    if any(
        keyword in error_lower for keyword in ("rate limit", "rate_limit", "timeout", "timed out")
    ):
        return "llm_error"
    if any(keyword in error_lower for keyword in ("validation", "invalid", "mismatch")):
        return "validation_error"
    if "cancelled" in error_lower or "cancel" in error_lower:
        return "cancelled"
    if "provider" in error_lower or "api key" in error_lower or "auth" in error_lower:
        return "provider_config_error"
    return "unknown"


def classify_result_error(result: Any) -> str:
    """Classify an error reported by a local extraction result."""
    return classify_error(result.error or "", result.status_code)


def recalculate_run_usage_from_extractions(session: Session, run_id: str) -> None:
    """Recalculate run token totals and stage usage from persisted extractions."""
    run = session.get(AnalysisRun, run_id)
    if run is None:
        return

    all_extractions = session.exec(
        select(LocalExtraction).where(LocalExtraction.run_id == run_id)
    ).all()
    total_prompt = sum(extraction.prompt_tokens or 0 for extraction in all_extractions)
    total_completion = sum(extraction.completion_tokens or 0 for extraction in all_extractions)
    total_all = sum(extraction.total_tokens or 0 for extraction in all_extractions)
    aggregate_reasoning = sum(extraction.reasoning_tokens or 0 for extraction in all_extractions)
    aggregate_cache_hit = sum(
        extraction.prompt_cache_hit_tokens or 0 for extraction in all_extractions
    )
    aggregate_cache_miss = sum(
        extraction.prompt_cache_miss_tokens or 0 for extraction in all_extractions
    )
    aggregate_unavailable = sum(
        extraction.usage_unavailable_attempts or 0 for extraction in all_extractions
    )

    run.prompt_tokens = total_prompt
    run.completion_tokens = total_completion
    run.total_tokens = total_all
    session.add(run)

    metadata = run.get_metadata()
    metadata["usage_by_stage"] = {
        "extraction": {
            "prompt_tokens": total_prompt,
            "completion_tokens": total_completion,
            "total_tokens": total_all,
            "reasoning_tokens": aggregate_reasoning,
            "prompt_cache_hit_tokens": aggregate_cache_hit,
            "prompt_cache_miss_tokens": aggregate_cache_miss,
            "usage_unavailable_attempts": aggregate_unavailable,
        },
        "merge": 0,
        "final": 0,
    }
    run.set_metadata(metadata)
    session.add(run)
    session.commit()


def clear_atoms_for_chunk(session: Session, run_id: str, chunk_id: str) -> int:
    """Delete the run's normalized atoms for one chunk."""
    from models.extracted_atom import ExtractedAtom

    atoms = session.exec(
        select(ExtractedAtom).where(
            ExtractedAtom.run_id == run_id,
            ExtractedAtom.chunk_id == chunk_id,
        )
    ).all()
    count = len(atoms)
    for atom in atoms:
        session.delete(atom)
    return count


def retry_failed_extractions(session: Session, run_id: str) -> dict:
    """Retry failed extraction rows, then rebuild merge and final outputs."""
    from models.chunk import Chunk

    run = session.get(AnalysisRun, run_id)
    if run is None:
        raise ValueError(f"AnalysisRun not found: {run_id}")

    failed_extractions = session.exec(
        select(LocalExtraction).where(
            LocalExtraction.run_id == run_id,
            LocalExtraction.status == "failed",
        )
    ).all()

    if not failed_extractions:
        return {
            "retried": 0,
            "succeeded": 0,
            "failed": 0,
            "message": "No failed extractions",
        }

    config = run.get_effective_config()
    api_key = resolve_api_key(session, run.topic_id)
    model_name = config.get("model_name", "")
    base_url = config.get("base_url", "")
    temperature = config.get("temperature") or 0.1
    max_tokens = config.get("max_output_tokens") or 3072
    thinking_mode = config.get("thinking_mode", "disabled")

    chunk_ids = {extraction.chunk_id for extraction in failed_extractions if extraction.chunk_id}
    chunks = session.exec(select(Chunk).where(Chunk.id.in_(chunk_ids))).all()  # noqa: E711
    chunk_map = {chunk.id: chunk for chunk in chunks}
    chapter_titles_by_chunk_id = load_chapter_titles_by_chunk_id(session, chunks)

    retried = 0
    retry_succeeded = 0
    retry_failed = 0
    error_types: dict[str, int] = {}

    for extraction in failed_extractions:
        if not extraction.chunk_id or extraction.chunk_id not in chunk_map:
            continue
        chunk = chunk_map[extraction.chunk_id]
        retried += 1

        result = local_extraction_worker.run_local_extraction_for_chunk(
            chunk_id=chunk.id,
            chunk_text=chunk.text,
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            max_tokens=max_tokens,
            temperature=temperature,
            thinking_mode=thinking_mode,
            chapter_index=chunk.chapter_index,
            chunk_index=chunk.chunk_index,
            chapter_title=chapter_titles_by_chunk_id.get(chunk.id),
        )

        clear_atoms_for_chunk(session, run_id, chunk.id)

        extraction.status = "succeeded" if result.ok else "failed"
        extraction.attempt_count = (extraction.attempt_count or 0) + 1
        extraction.content_json = result.content_json
        extraction.error_message = result.error[:1000] if result.error else None
        extraction.confidence = 0.5
        extraction.prompt_tokens = (extraction.prompt_tokens or 0) + result.prompt_tokens
        extraction.completion_tokens = (
            extraction.completion_tokens or 0
        ) + result.completion_tokens
        extraction.total_tokens = (extraction.total_tokens or 0) + result.total_tokens
        extraction.model_used = result.model_used
        extraction.finished_at = _now()
        extraction.reasoning_tokens = (
            extraction.reasoning_tokens or 0
        ) + result.cumulative_reasoning_tokens
        extraction.prompt_cache_hit_tokens = (
            extraction.prompt_cache_hit_tokens or 0
        ) + result.cumulative_prompt_cache_hit_tokens
        extraction.prompt_cache_miss_tokens = (
            extraction.prompt_cache_miss_tokens or 0
        ) + result.cumulative_prompt_cache_miss_tokens
        extraction.usage_unavailable_attempts = (
            extraction.usage_unavailable_attempts or 0
        ) + result.usage_unavailable_attempts
        extraction.attempt_usage_json = serialize_attempts(result.attempts)
        session.add(extraction)
        session.flush()

        if result.ok:
            retry_succeeded += 1
            run.extraction_succeeded = (run.extraction_succeeded or 0) + 1
            run.extraction_failed = max(0, (run.extraction_failed or 0) - 1)
            if result.content_json:
                atom_normalizer.normalize_local_extraction(
                    extraction_id=extraction.id,
                    run_id=run_id,
                    topic_id=run.topic_id,
                    chunk_id=chunk.id,
                    content_json_str=result.content_json,
                    session=session,
                )
        else:
            retry_failed += 1
            error_type = classify_result_error(result)
            error_types[error_type] = error_types.get(error_type, 0) + 1

    session.commit()

    run_merge_and_final(session, run_id)
    recalculate_run_usage_from_extractions(session, run_id)

    run = session.get(AnalysisRun, run_id)
    if run:
        metadata = run.get_metadata()
        metadata["retry_summary"] = {
            "retried": retried,
            "succeeded": retry_succeeded,
            "failed": retry_failed,
            "error_types": error_types,
        }
        run.set_metadata(metadata)
        session.add(run)
        session.commit()

    return {
        "retried": retried,
        "succeeded": retry_succeeded,
        "failed": retry_failed,
        "error_types": error_types,
    }


def run_merge_and_final(session: Session, run_id: str) -> None:
    """Rebuild deterministic merge and final stages after retry or resume."""
    from services.final_output_service import run_final_output_stage
    from services.merge_service import run_merge_stage

    run = session.get(AnalysisRun, run_id)
    if run is None:
        return

    requested_types = run.get_requested_types()
    valid_merge = {
        "overview",
        "characters",
        "relations",
        "events",
        "causality",
        "themes",
        "worldbuilding",
        "foreshadowing",
    }
    merge_types = [
        analysis_type for analysis_type in requested_types if analysis_type in valid_merge
    ]

    merge_succeeded = 0
    merge_failed = 0
    if merge_types:
        merge_summaries = run_merge_stage(session, run_id, requested_types=merge_types)
        merge_succeeded = sum(
            1
            for summary in merge_summaries
            if summary.atom_count >= 0
            and not any("Merge failed:" in warning for warning in summary.warnings)
        )
        merge_failed = sum(
            1
            for summary in merge_summaries
            if any("Merge failed:" in warning for warning in summary.warnings)
        )

    final_types = {"overview", "characters", "relations", "events", "causality", "themes"}
    final_merge_types = [
        analysis_type for analysis_type in merge_types if analysis_type in final_types
    ]
    if final_merge_types and merge_succeeded > 0:
        run_final_output_stage(session, run_id, requested_types=final_merge_types)

    run = session.get(AnalysisRun, run_id)
    if run:
        run.merge_succeeded = merge_succeeded
        run.merge_failed = merge_failed
        if run.extraction_succeeded == 0:
            run.status = JobStatus.FAILED
        elif (
            (run.extraction_failed or 0) == 0 and merge_failed == 0 and (run.final_failed or 0) == 0
        ):
            run.status = JobStatus.SUCCEEDED
        else:
            run.status = JobStatus.PARTIAL_SUCCESS
        run.finished_at = _now()
        session.add(run)
        session.commit()


def resume_analysis_run(
    session: Session,
    run_id: str,
    retry_failed: bool = True,
) -> AnalysisRun:
    """Run missing chunks and optionally retry failures without rerunning success."""
    from models.chunk import Chunk

    run = session.get(AnalysisRun, run_id)
    if run is None:
        raise ValueError(f"AnalysisRun not found: {run_id}")

    if run.status == JobStatus.CANCELLED:
        raise ValueError("Cannot resume a cancelled run")

    if run.status in (JobStatus.SUCCEEDED,):
        return run

    selection = run.get_chunk_selection()
    selected_ids = selection.get("selected_chunk_ids", [])
    if not selected_ids:
        raise ValueError("No chunk selection found; cannot resume")

    existing = session.exec(select(LocalExtraction).where(LocalExtraction.run_id == run_id)).all()
    succeeded_chunks = {
        extraction.chunk_id for extraction in existing if extraction.status == "succeeded"
    }
    failed_chunks = {
        extraction.chunk_id for extraction in existing if extraction.status == "failed"
    }
    has_extraction = succeeded_chunks | failed_chunks

    missing_ids = [chunk_id for chunk_id in selected_ids if chunk_id not in has_extraction]
    retry_ids = [chunk_id for chunk_id in failed_chunks if retry_failed]

    to_run = set(missing_ids) | set(retry_ids)
    if not to_run:
        run_merge_and_final(session, run_id)
        return session.get(AnalysisRun, run_id)

    chunks = session.exec(select(Chunk).where(Chunk.id.in_(to_run))).all()  # noqa: E711
    chunk_map = {chunk.id: chunk for chunk in chunks}
    chapter_titles_by_chunk_id = load_chapter_titles_by_chunk_id(session, chunks)

    config = run.get_effective_config()
    api_key = resolve_api_key(session, run.topic_id)
    model_name = config.get("model_name", "")
    base_url = config.get("base_url", "")
    temperature = config.get("temperature") or 0.1
    max_tokens = config.get("max_output_tokens") or 3072
    thinking_mode = config.get("thinking_mode", "disabled")

    for chunk_id in to_run:
        chunk = chunk_map.get(chunk_id)
        if chunk is None:
            continue

        if chunk_id in retry_ids:
            clear_atoms_for_chunk(session, run_id, chunk.id)

        result = local_extraction_worker.run_local_extraction_for_chunk(
            chunk_id=chunk.id,
            chunk_text=chunk.text,
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            max_tokens=max_tokens,
            temperature=temperature,
            thinking_mode=thinking_mode,
            chapter_index=chunk.chapter_index,
            chunk_index=chunk.chunk_index,
            chapter_title=chapter_titles_by_chunk_id.get(chunk.id),
        )

        extraction = session.exec(
            select(LocalExtraction).where(
                LocalExtraction.run_id == run_id,
                LocalExtraction.chunk_id == chunk.id,
            )
        ).first()
        if extraction is None:
            extraction = LocalExtraction(
                run_id=run_id,
                topic_id=run.topic_id,
                chunk_id=chunk.id,
            )
            session.add(extraction)
            session.flush()

        extraction.status = "succeeded" if result.ok else "failed"
        extraction.attempt_count = (extraction.attempt_count or 0) + 1
        extraction.content_json = result.content_json
        extraction.error_message = result.error[:1000] if result.error else None
        extraction.confidence = 0.5
        extraction.prompt_tokens = (extraction.prompt_tokens or 0) + result.prompt_tokens
        extraction.completion_tokens = (
            extraction.completion_tokens or 0
        ) + result.completion_tokens
        extraction.total_tokens = (extraction.total_tokens or 0) + result.total_tokens
        extraction.model_used = result.model_used
        extraction.finished_at = _now()
        extraction.reasoning_tokens = (
            extraction.reasoning_tokens or 0
        ) + result.cumulative_reasoning_tokens
        extraction.prompt_cache_hit_tokens = (
            extraction.prompt_cache_hit_tokens or 0
        ) + result.cumulative_prompt_cache_hit_tokens
        extraction.prompt_cache_miss_tokens = (
            extraction.prompt_cache_miss_tokens or 0
        ) + result.cumulative_prompt_cache_miss_tokens
        extraction.usage_unavailable_attempts = (
            extraction.usage_unavailable_attempts or 0
        ) + result.usage_unavailable_attempts
        extraction.attempt_usage_json = serialize_attempts(result.attempts)
        session.add(extraction)
        session.flush()

        if result.ok and result.content_json:
            atom_normalizer.normalize_local_extraction(
                extraction_id=extraction.id,
                run_id=run_id,
                topic_id=run.topic_id,
                chunk_id=chunk.id,
                content_json_str=result.content_json,
                session=session,
            )

    all_extractions = session.exec(
        select(LocalExtraction).where(LocalExtraction.run_id == run_id)
    ).all()
    total_succeeded = sum(1 for extraction in all_extractions if extraction.status == "succeeded")
    total_failed = sum(1 for extraction in all_extractions if extraction.status == "failed")

    run = session.get(AnalysisRun, run_id)
    if run:
        run.extraction_succeeded = total_succeeded
        run.extraction_failed = total_failed
        session.add(run)

    session.commit()

    run_merge_and_final(session, run_id)
    recalculate_run_usage_from_extractions(session, run_id)

    return session.get(AnalysisRun, run_id)
