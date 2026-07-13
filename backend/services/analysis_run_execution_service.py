"""Initial AnalysisRun extraction, merge, and final-output execution."""

import json
import time
from collections.abc import Callable
from concurrent.futures import as_completed
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from models.analysis_run import AnalysisRun
from models.chapter import Chapter
from models.chunk import Chunk
from models.enums import JobStatus
from models.local_extraction import LocalExtraction
from services import atom_normalizer, local_extraction_worker


def _now() -> datetime:
    return datetime.now(timezone.utc)


def load_chapter_titles_by_chunk_id(
    session: Session,
    chunks: list[Chunk],
) -> dict[str, str]:
    """Resolve chapter titles by the selected Chunk's explicit chapter foreign key."""
    chapter_ids = {chunk.chapter_id for chunk in chunks if chunk.chapter_id}
    if not chapter_ids:
        return {}

    chapters = session.exec(select(Chapter).where(Chapter.id.in_(chapter_ids))).all()
    title_by_chapter_id = {chapter.id: chapter.title for chapter in chapters}
    return {
        chunk.id: title_by_chapter_id[chunk.chapter_id]
        for chunk in chunks
        if chunk.chapter_id in title_by_chapter_id
    }


def execute_run_impl(
    run_id: str,
    engine: Engine,
    executor_factory: Callable[..., Any],
) -> None:
    """Execute the initial extraction, merge, and final stages for one run."""
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        if run is None or run.status not in (JobStatus.PENDING, JobStatus.RUNNING):
            return

        run.status = JobStatus.RUNNING
        run.started_at = run.started_at or _now()
        session.add(run)
        session.commit()

        config = run.get_effective_config()
        parallelism = min(max(config.get("analysis_parallelism", 3), 1), 6)
        model_name = config.get("model_name", "")
        base_url = config.get("base_url", "")
        api_key = resolve_api_key(session, run.topic_id)
        temperature = config.get("temperature") or 0.1
        max_tokens = config.get("max_output_tokens") or 3072
        thinking_mode = config.get("thinking_mode", "disabled")

        selection = run.get_chunk_selection()
        selected_chunk_ids = selection.get("selected_chunk_ids", [])
        if not selected_chunk_ids:
            run.status = JobStatus.FAILED
            run.error_message = "No chunks selected"
            run.finished_at = _now()
            session.add(run)
            session.commit()
            return

        id_to_chunk = {}
        all_chunks = session.exec(
            select(Chunk).where(Chunk.id.in_(selected_chunk_ids))  # noqa: E711
        ).all()
        for chunk in all_chunks:
            id_to_chunk[chunk.id] = chunk
        selected = [
            id_to_chunk[chunk_id] for chunk_id in selected_chunk_ids if chunk_id in id_to_chunk
        ]

        if not selected:
            run.status = JobStatus.FAILED
            run.error_message = "No chunks selected"
            run.finished_at = _now()
            session.add(run)
            session.commit()
            return

        chapter_titles_by_chunk_id = load_chapter_titles_by_chunk_id(session, selected)

    stage_start = time.monotonic()
    extraction_start = stage_start
    succeeded = 0
    failed = 0
    total_tokens = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    failed_chunks: list[dict] = []

    with executor_factory(max_workers=parallelism, thread_name_prefix="v2-extract") as executor:
        futures = {}
        for chunk in selected:
            future = executor.submit(
                local_extraction_worker.run_local_extraction_for_chunk,
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
            futures[future] = chunk.id

        for future in as_completed(futures):
            chunk_id = futures[future]

            with Session(engine) as session:
                run = session.get(AnalysisRun, run_id)
                if run is None or run.status == JobStatus.CANCELLED:
                    executor.shutdown(wait=False, cancel_futures=True)
                    return

            try:
                result = future.result()
            except Exception as exc:
                failed += 1
                failed_chunks.append({"chunk_id": chunk_id, "error": str(exc)[:200]})
                with Session(engine) as session:
                    save_extraction(
                        session,
                        run_id,
                        run.topic_id,
                        chunk_id,
                        ok=False,
                        error=str(exc),
                    )
                    session.commit()
                continue

            with Session(engine) as session:
                save_extraction(
                    session,
                    run_id,
                    run.topic_id,
                    chunk_id,
                    ok=result.ok,
                    content_json=result.content_json,
                    parsed_json=result.parsed_json,
                    error=result.error,
                    prompt_tokens=result.prompt_tokens,
                    completion_tokens=result.completion_tokens,
                    total_tokens=result.total_tokens,
                    model_used=result.model_used,
                    retry_count=result.retry_count,
                    reasoning_tokens=result.cumulative_reasoning_tokens,
                    prompt_cache_hit_tokens=result.cumulative_prompt_cache_hit_tokens,
                    prompt_cache_miss_tokens=result.cumulative_prompt_cache_miss_tokens,
                    usage_unavailable_attempts=result.usage_unavailable_attempts,
                    attempt_usage_json=serialize_attempts(result.attempts),
                )
                if result.ok:
                    succeeded += 1
                else:
                    failed += 1
                    failed_chunks.append(
                        {
                            "chunk_id": chunk_id,
                            "error": (result.error or "")[:200],
                        }
                    )
                total_tokens += result.total_tokens
                total_prompt_tokens += result.prompt_tokens
                total_completion_tokens += result.completion_tokens

                run = session.get(AnalysisRun, run_id)
                if run is None or run.status == JobStatus.CANCELLED:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                run.extraction_succeeded = succeeded
                run.extraction_failed = failed
                run.total_tokens = total_tokens
                run.prompt_tokens = total_prompt_tokens
                run.completion_tokens = total_completion_tokens
                run.progress_current = succeeded + failed
                session.add(run)
                session.commit()

    extraction_elapsed = round(time.monotonic() - extraction_start, 3)

    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        if run is None:
            return

        if run.status == JobStatus.CANCELLED:
            run.finished_at = run.finished_at or _now()
            session.add(run)
            session.commit()
            return

        run.extraction_succeeded = succeeded
        run.extraction_failed = failed
        run.total_tokens = total_tokens
        run.prompt_tokens = total_prompt_tokens
        run.completion_tokens = total_completion_tokens
        run.progress_current = succeeded + failed

        if succeeded == 0:
            run.status = JobStatus.FAILED
            run.error_message = run.error_message or "All extractions failed"
            run.finished_at = _now()
            run.set_metadata(
                {
                    "stage": "extraction_failed",
                    "failed_chunks": failed_chunks,
                    "warnings": [],
                }
            )
            session.add(run)
            session.commit()
            return

        merge_start = time.monotonic()
        extraction_tokens = run.total_tokens or 0
        requested_types = run.get_requested_types()
        merge_types = [
            analysis_type
            for analysis_type in requested_types
            if analysis_type
            in {
                "overview",
                "characters",
                "relations",
                "events",
                "causality",
                "themes",
                "worldbuilding",
                "foreshadowing",
            }
        ]

        if merge_types:
            from services.merge_service import run_merge_stage

            merge_summaries = run_merge_stage(session, run_id, requested_types=merge_types)
            merge_succeeded_count = sum(
                1
                for summary in merge_summaries
                if summary.atom_count >= 0
                and not any("Merge failed:" in warning for warning in summary.warnings)
            )
            merge_failed_count = sum(
                1
                for summary in merge_summaries
                if any("Merge failed:" in warning for warning in summary.warnings)
            )
            merge_warnings: list[str] = []
            for summary in merge_summaries:
                merge_warnings.extend(summary.warnings)

            run = session.get(AnalysisRun, run_id)
            if run:
                run.merge_succeeded = merge_succeeded_count
                run.merge_failed = merge_failed_count
                run.progress_current = (
                    succeeded + failed + merge_succeeded_count + merge_failed_count
                )
        else:
            merge_summaries = []
            merge_succeeded_count = 0
            merge_failed_count = 0
            merge_warnings = []

        merge_elapsed = round(time.monotonic() - merge_start, 3)

        final_start = time.monotonic()
        final_summaries: list = []
        final_succeeded_count = 0
        final_failed_count = 0
        final_warnings: list[str] = []

        if merge_succeeded_count > 0:
            final_output_types = {
                "overview",
                "characters",
                "relations",
                "events",
                "causality",
                "themes",
            }
            final_types = [
                analysis_type
                for analysis_type in merge_types
                if analysis_type in final_output_types
            ]

            if final_types:
                from services.final_output_service import run_final_output_stage

                final_summaries = run_final_output_stage(
                    session,
                    run_id,
                    requested_types=final_types,
                )
                for summary in final_summaries:
                    final_warnings.extend(summary.warnings)

                run = session.get(AnalysisRun, run_id)
                if run:
                    final_succeeded_count = run.final_succeeded or 0
                    final_failed_count = run.final_failed or 0
                    final_skipped_count = run.final_skipped or 0
                    run.progress_current = (
                        succeeded
                        + failed
                        + merge_succeeded_count
                        + merge_failed_count
                        + final_succeeded_count
                        + final_failed_count
                        + final_skipped_count
                    )

        final_elapsed = round(time.monotonic() - final_start, 3)
        run = session.get(AnalysisRun, run_id)
        if run and run.status != JobStatus.CANCELLED:
            if succeeded == 0:
                run.status = JobStatus.FAILED
            elif failed == 0 and merge_failed_count == 0 and final_failed_count == 0:
                run.status = JobStatus.SUCCEEDED
            else:
                run.status = JobStatus.PARTIAL_SUCCESS
            run.finished_at = _now()

            failed_merge_types = [
                summary.merge_type
                for summary in merge_summaries
                if any("Merge failed:" in warning for warning in summary.warnings)
            ]
            failed_final_types = [
                summary.output_type
                for summary in final_summaries
                if any("Final output failed:" in warning for warning in summary.warnings)
            ]

            all_extractions = session.exec(
                select(LocalExtraction).where(LocalExtraction.run_id == run_id)
            ).all()
            aggregate_reasoning = sum(
                extraction.reasoning_tokens or 0 for extraction in all_extractions
            )
            aggregate_cache_hit = sum(
                extraction.prompt_cache_hit_tokens or 0 for extraction in all_extractions
            )
            aggregate_cache_miss = sum(
                extraction.prompt_cache_miss_tokens or 0 for extraction in all_extractions
            )
            aggregate_unavailable = sum(
                extraction.usage_unavailable_attempts or 0 for extraction in all_extractions
            )

            work_id = selection.get("work_id")
            if work_id and run.status == JobStatus.SUCCEEDED:
                from models.work import Work

                work = session.get(Work, work_id)
                if work is not None:
                    work.status = "analyzed"
                    session.add(work)

            run.set_metadata(
                {
                    "stage": "completed",
                    "stage_timings": {
                        "extraction": extraction_elapsed,
                        "merge": merge_elapsed,
                        "final": final_elapsed,
                    },
                    "failed_chunks": failed_chunks,
                    "failed_merge_types": failed_merge_types,
                    "failed_final_types": failed_final_types,
                    "merge_summaries": [
                        {
                            "type": summary.merge_type,
                            "atoms": summary.atom_count,
                            "merged": summary.merged_count,
                        }
                        for summary in merge_summaries
                    ],
                    "final_summaries": [
                        {"type": summary.output_type, "items": summary.item_count}
                        for summary in final_summaries
                    ],
                    "usage_by_stage": {
                        "extraction": {
                            "prompt_tokens": total_prompt_tokens,
                            "completion_tokens": total_completion_tokens,
                            "total_tokens": extraction_tokens,
                            "reasoning_tokens": aggregate_reasoning,
                            "prompt_cache_hit_tokens": aggregate_cache_hit,
                            "prompt_cache_miss_tokens": aggregate_cache_miss,
                            "usage_unavailable_attempts": aggregate_unavailable,
                        },
                        "merge": 0,
                        "final": 0,
                    },
                    "warnings": merge_warnings + final_warnings,
                }
            )
            session.add(run)
            session.commit()


def serialize_attempts(attempts: list) -> str | None:
    """Serialize attempts, accepting worker objects and plain dictionaries."""
    if not attempts:
        return None
    serialized = []
    for attempt in attempts:
        if hasattr(attempt, "to_dict"):
            serialized.append(attempt.to_dict())
        elif isinstance(attempt, dict):
            serialized.append(attempt)
        else:
            serialized.append(str(attempt))
    return json.dumps(serialized, ensure_ascii=False)


def save_extraction(
    session: Session,
    run_id: str,
    topic_id: str,
    chunk_id: str,
    ok: bool,
    content_json: str | None = None,
    parsed_json: dict | None = None,
    error: str | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    model_used: str | None = None,
    retry_count: int = 0,
    force: bool = False,
    reasoning_tokens: int = 0,
    prompt_cache_hit_tokens: int = 0,
    prompt_cache_miss_tokens: int = 0,
    usage_unavailable_attempts: int = 0,
    attempt_usage_json: str | None = None,
) -> None:
    """Persist one extraction and normalize successful structured atoms."""
    if ok and not force:
        existing = session.exec(
            select(LocalExtraction).where(
                LocalExtraction.run_id == run_id,
                LocalExtraction.chunk_id == chunk_id,
                LocalExtraction.status == "succeeded",
            )
        ).first()
        if existing is not None:
            return

    extraction = LocalExtraction(
        run_id=run_id,
        topic_id=topic_id,
        chunk_id=chunk_id,
        status="succeeded" if ok else "failed",
        attempt_count=retry_count + 1,
        content_json=content_json,
        confidence=0.5,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        model_used=model_used,
        error_message=error[:1000] if error else None,
        started_at=_now(),
        finished_at=_now(),
        reasoning_tokens=reasoning_tokens,
        prompt_cache_hit_tokens=prompt_cache_hit_tokens,
        prompt_cache_miss_tokens=prompt_cache_miss_tokens,
        usage_unavailable_attempts=usage_unavailable_attempts,
        attempt_usage_json=attempt_usage_json,
    )
    session.add(extraction)
    session.flush()

    if ok and content_json:
        atom_normalizer.normalize_local_extraction(
            extraction_id=extraction.id,
            run_id=run_id,
            topic_id=topic_id,
            chunk_id=chunk_id,
            content_json_str=content_json,
            session=session,
        )


def resolve_api_key(session: Session, topic_id: str) -> str:
    """Resolve the topic provider API key using the established precedence."""
    from models.model_provider import ModelProvider
    from models.topic import Topic
    from models.topic_provider_config import TopicProviderConfig

    topic_config = session.exec(
        select(TopicProviderConfig).where(TopicProviderConfig.topic_id == topic_id)
    ).first()
    if topic_config and topic_config.provider_id:
        provider = session.get(ModelProvider, topic_config.provider_id)
        if provider and provider.api_key:
            return provider.api_key

    topic = session.get(Topic, topic_id)
    if topic and topic.provider_id:
        provider = session.get(ModelProvider, topic.provider_id)
        if provider and provider.api_key:
            return provider.api_key

    provider = session.exec(
        select(ModelProvider).where(ModelProvider.is_default == True)  # noqa: E712
    ).first()
    if provider and provider.api_key:
        return provider.api_key

    raise ValueError("No provider configured")
