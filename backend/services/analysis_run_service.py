"""AnalysisRun lifecycle facade and process-local executor ownership."""

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.engine import Engine
from sqlmodel import Session, func, select

from models.analysis_run import AnalysisRun
from models.enums import AnalysisMode, JobStatus
from models.local_extraction import LocalExtraction
from services import analysis_run_continuation_service as _continuation
from services import analysis_run_execution_service as _execution

_EXECUTOR_STATE_LOCK = threading.RLock()
_ACTIVE_EXECUTORS_BY_TOPIC: dict[str, str] = {}
_ACTIVE_EXECUTOR_RUNS: set[str] = set()
INTERRUPTED_RUN_MESSAGE = (
    "Analysis run was interrupted by a backend restart. Resume it explicitly to "
    "continue without re-running succeeded chunks."
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_analysis_run(
    session: Session,
    topic_id: str,
    mode: str = AnalysisMode.PREVIEW,
    requested_types: list[str] | None = None,
    limit_chunks: int | None = None,
    chunk_index_start: int | None = None,
    chunk_index_end: int | None = None,
    chapter_index_start: int | None = None,
    chapter_index_end: int | None = None,
    force: bool = False,
    work_id: str | None = None,
) -> AnalysisRun:
    """Create one pending run while serializing the active-run check and insert."""
    with _EXECUTOR_STATE_LOCK:
        return _create_analysis_run(
            session,
            topic_id,
            mode=mode,
            requested_types=requested_types,
            limit_chunks=limit_chunks,
            chunk_index_start=chunk_index_start,
            chunk_index_end=chunk_index_end,
            chapter_index_start=chapter_index_start,
            chapter_index_end=chapter_index_end,
            force=force,
            work_id=work_id,
        )


def _create_analysis_run(
    session: Session,
    topic_id: str,
    mode: str = AnalysisMode.PREVIEW,
    requested_types: list[str] | None = None,
    limit_chunks: int | None = None,
    chunk_index_start: int | None = None,
    chunk_index_end: int | None = None,
    chapter_index_start: int | None = None,
    chapter_index_end: int | None = None,
    force: bool = False,
    work_id: str | None = None,
) -> AnalysisRun:
    """Create and persist an AnalysisRun for one Topic and optional Work."""
    from services.analysis_selection_service import (
        FINAL_ANALYSIS_TYPES,
        normalize_requested_types,
        select_chunks_for_analysis,
        validate_analysis_mode,
    )
    from services.provider_config_service import get_effective_config

    validate_analysis_mode(mode)

    if topic_id in _ACTIVE_EXECUTORS_BY_TOPIC:
        raise ValueError("Analysis is already running for this topic")
    active_run = session.exec(
        select(AnalysisRun)
        .where(AnalysisRun.topic_id == topic_id)
        .where(AnalysisRun.status.in_([JobStatus.PENDING, JobStatus.RUNNING]))  # type: ignore[arg-type]
    ).first()
    if active_run is not None:
        raise ValueError("Analysis is already running for this topic")

    document_id: str | None = None
    if work_id is not None:
        from models.document import Document

        document = session.exec(select(Document).where(Document.work_id == work_id)).first()
        if document is None:
            raise ValueError("No document found for this Work")
        document_id = document.id

    from models.chunk import Chunk

    chunk_base = select(Chunk).where(Chunk.topic_id == topic_id)
    if document_id is not None:
        chunk_base = chunk_base.where(Chunk.document_id == document_id)
    chunk = session.exec(chunk_base.limit(1)).first()
    if chunk is None:
        raise ValueError("No chunks found; parse document first")

    selected, selection_info = select_chunks_for_analysis(
        session,
        topic_id,
        mode,
        limit_chunks=limit_chunks,
        range_start=chunk_index_start,
        range_end=chunk_index_end,
        chapter_start=chapter_index_start,
        chapter_end=chapter_index_end,
        document_id=document_id,
    )

    selection_info["selected_chunk_ids"] = [selected_chunk.id for selected_chunk in selected]
    if work_id is not None:
        selection_info["work_id"] = work_id

    effective = get_effective_config(session, topic_id)
    if not effective or not effective.is_ready:
        raise ValueError("No provider configured for this topic")

    types = normalize_requested_types(requested_types)
    merge_requested_types = types.copy()
    extraction_total = len(selected)
    merge_total = len(merge_requested_types)
    final_requested_types = [
        analysis_type
        for analysis_type in merge_requested_types
        if analysis_type in FINAL_ANALYSIS_TYPES
    ]
    final_total = len(final_requested_types)
    progress_total = extraction_total + merge_total + final_total

    run = AnalysisRun(
        topic_id=topic_id,
        mode=mode,
        status=JobStatus.PENDING,
        extraction_total=extraction_total,
        merge_total=merge_total,
        final_total=final_total,
        progress_total=progress_total,
        model_used=effective.model_name,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )
    run.set_requested_types(types)
    run.set_chunk_selection(selection_info)
    run.set_effective_config(
        {
            "model_name": effective.model_name or "",
            "base_url": effective.base_url or "",
            "temperature": effective.temperature,
            "max_output_tokens": effective.max_output_tokens or 3072,
            "thinking_mode": effective.thinking_mode,
            "analysis_parallelism": effective.analysis_parallelism,
        }
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def start_analysis_run(run_id: str, engine: Engine | None = None) -> bool:
    """Start a pending run once; return False when it is not startable."""
    engine = _resolve_engine(engine)
    with _EXECUTOR_STATE_LOCK:
        with Session(engine) as session:
            run = session.get(AnalysisRun, run_id)
            if run is None:
                raise ValueError(f"AnalysisRun not found: {run_id}")
            if run.status != JobStatus.PENDING or not _executor_is_available(run):
                return False
            return _launch_registered_executor(
                run,
                _execute_run,
                (),
                engine,
                name_prefix="analysis-run",
            )


def recover_interrupted_analysis_runs(engine: Engine | None = None) -> list[str]:
    """Mark orphaned active runs resumable without making automatic LLM calls."""
    engine = _resolve_engine(engine)
    recovered: list[str] = []
    recovered_at = _now()
    with _EXECUTOR_STATE_LOCK:
        with Session(engine) as session:
            runs = session.exec(
                select(AnalysisRun).where(AnalysisRun.status == JobStatus.RUNNING)
            ).all()
            for run in runs:
                if run.id in _ACTIVE_EXECUTOR_RUNS:
                    continue
                previous_status = run.status
                metadata = run.get_metadata()
                metadata["startup_recovery"] = {
                    "previous_status": previous_status,
                    "recovered_at": recovered_at.isoformat(),
                    "reason": "backend_restart",
                    "action": "marked_failed",
                    "resume_available": True,
                }
                run.set_metadata(metadata)
                run.status = JobStatus.FAILED
                run.error_message = INTERRUPTED_RUN_MESSAGE
                run.finished_at = recovered_at
                run.updated_at = recovered_at
                session.add(run)
                recovered.append(run.id)
            if recovered:
                session.commit()
    return recovered


def _execute_run(run_id: str, engine: Engine | None = None) -> None:
    """Run initial analysis in the registered background executor."""
    engine = _resolve_engine(engine)
    try:
        _execute_run_impl(run_id, engine)
    except Exception as exc:
        _fail_run(run_id, engine, str(exc))


def _fail_run(run_id: str, engine: Engine, error: str) -> None:
    """Record an unhandled executor failure without overwriting terminal work."""
    try:
        with Session(engine) as session:
            run = session.get(AnalysisRun, run_id)
            if run is None:
                return
            protected = {
                JobStatus.SUCCEEDED,
                JobStatus.CANCELLED,
                JobStatus.PARTIAL_SUCCESS,
            }
            if run.status in protected:
                return
            if run.finished_at is not None:
                metadata = run.get_metadata()
                if metadata.get("stage") == "completed":
                    return
            safe = _mask_api_keys_in_error(session, error)[:1000]
            run.status = JobStatus.FAILED
            run.error_message = safe
            run.finished_at = _now()
            session.add(run)
            session.commit()
    except Exception:
        pass


def _mask_api_keys_in_error(session: Session, error: str) -> str:
    """Replace all known provider keys in an error with masked values."""
    from models.model_provider import ModelProvider, mask_api_key

    result = error
    try:
        providers = session.exec(select(ModelProvider)).all()
        for provider in providers:
            if provider.api_key and len(provider.api_key) > 4 and provider.api_key in result:
                result = result.replace(provider.api_key, mask_api_key(provider.api_key))
    except Exception:
        pass
    return result


def _execute_run_impl(run_id: str, engine: Engine) -> None:
    """Compatibility entry point for the initial execution implementation."""
    _execution.execute_run_impl(
        run_id,
        engine,
        executor_factory=ThreadPoolExecutor,
    )


def _serialize_attempts(attempts: list) -> str | None:
    """Compatibility entry point for extraction attempt serialization."""
    return _execution.serialize_attempts(attempts)


def _save_extraction(
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
    """Compatibility entry point for extraction persistence."""
    _execution.save_extraction(
        session,
        run_id,
        topic_id,
        chunk_id,
        ok,
        content_json=content_json,
        parsed_json=parsed_json,
        error=error,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        model_used=model_used,
        retry_count=retry_count,
        force=force,
        reasoning_tokens=reasoning_tokens,
        prompt_cache_hit_tokens=prompt_cache_hit_tokens,
        prompt_cache_miss_tokens=prompt_cache_miss_tokens,
        usage_unavailable_attempts=usage_unavailable_attempts,
        attempt_usage_json=attempt_usage_json,
    )


def _resolve_api_key(session: Session, topic_id: str) -> str:
    """Compatibility entry point for provider key resolution."""
    return _execution.resolve_api_key(session, topic_id)


def get_analysis_run_status(session: Session, run_id: str) -> dict | None:
    """Return run status with extraction, merge, and final output summary."""
    from models.analysis_output import AnalysisOutput

    run = session.get(AnalysisRun, run_id)
    if run is None:
        return None

    extractions = session.exec(
        select(LocalExtraction).where(LocalExtraction.run_id == run_id)
    ).all()
    aggregate_reasoning = sum(extraction.reasoning_tokens or 0 for extraction in extractions)
    aggregate_cache_hit = sum(extraction.prompt_cache_hit_tokens or 0 for extraction in extractions)
    aggregate_cache_miss = sum(
        extraction.prompt_cache_miss_tokens or 0 for extraction in extractions
    )
    aggregate_unavailable = sum(
        extraction.usage_unavailable_attempts or 0 for extraction in extractions
    )

    all_outputs = session.exec(select(AnalysisOutput).where(AnalysisOutput.run_id == run_id)).all()
    merge_outputs = [output for output in all_outputs if output.output_type.startswith("merge_")]
    final_outputs = [
        output for output in all_outputs if not output.output_type.startswith("merge_")
    ]

    metadata = run.get_metadata()
    selection = run.get_chunk_selection()

    return {
        "run": {
            "id": run.id,
            "topic_id": run.topic_id,
            "mode": run.mode,
            "status": run.status,
            "progress_current": run.progress_current,
            "progress_total": run.progress_total,
            "extraction_total": run.extraction_total,
            "extraction_succeeded": run.extraction_succeeded,
            "extraction_failed": run.extraction_failed,
            "merge_total": run.merge_total,
            "merge_succeeded": run.merge_succeeded,
            "merge_failed": run.merge_failed,
            "final_total": run.final_total or 0,
            "final_succeeded": run.final_succeeded or 0,
            "final_failed": run.final_failed or 0,
            "final_skipped": run.final_skipped or 0,
            "total_tokens": run.total_tokens,
            "prompt_tokens": run.prompt_tokens,
            "completion_tokens": run.completion_tokens,
            "reasoning_tokens": aggregate_reasoning,
            "prompt_cache_hit_tokens": aggregate_cache_hit,
            "prompt_cache_miss_tokens": aggregate_cache_miss,
            "usage_unavailable_attempts": aggregate_unavailable,
            "model_used": run.model_used,
            "work_id": selection.get("work_id"),
            "error_message": run.error_message,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        },
        "extractions": [
            {
                "id": extraction.id,
                "chunk_id": extraction.chunk_id,
                "status": extraction.status,
                "attempt_count": extraction.attempt_count,
                "error_message": extraction.error_message,
            }
            for extraction in extractions
        ],
        "merge": {
            "total": run.merge_total or 0,
            "succeeded": run.merge_succeeded or 0,
            "failed": run.merge_failed or 0,
            "outputs": [
                {
                    "id": output.id,
                    "output_type": output.output_type,
                    "title": output.title,
                }
                for output in merge_outputs
            ],
            "warnings": metadata.get("warnings", []),
        },
        "final": {
            "total": run.final_total or 0,
            "succeeded": run.final_succeeded or 0,
            "failed": run.final_failed or 0,
            "skipped": run.final_skipped or 0,
            "outputs": [
                {
                    "id": output.id,
                    "output_type": output.output_type,
                    "title": output.title,
                }
                for output in final_outputs
            ],
        },
    }


def list_analysis_runs(
    session: Session,
    topic_id: str,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AnalysisRun], int]:
    """List Topic runs with SQL-level pagination, most recent first."""
    base = select(AnalysisRun).where(AnalysisRun.topic_id == topic_id)
    total = session.exec(select(func.count()).select_from(base.subquery())).one()
    runs = list(
        session.exec(base.order_by(AnalysisRun.created_at.desc()).offset(offset).limit(limit)).all()
    )
    return runs, total


def cancel_analysis_run(session: Session, run_id: str) -> AnalysisRun | None:
    """Cancel a pending or running analysis run."""
    run = session.get(AnalysisRun, run_id)
    if run is None:
        return None
    if run.status in (JobStatus.PENDING, JobStatus.RUNNING):
        run.status = JobStatus.CANCELLED
        run.finished_at = _now()
        session.add(run)
        session.commit()
        session.refresh(run)
    return run


def _classify_error(error: str, status_code: int | None = None) -> str:
    """Compatibility entry point for continuation error classification."""
    return _continuation.classify_error(error, status_code)


def _classify_result_error(result: Any) -> str:
    """Compatibility entry point for worker-result error classification."""
    return _continuation.classify_result_error(result)


def _recalculate_run_usage_from_extractions(session: Session, run_id: str) -> None:
    """Compatibility entry point for persisted usage recalculation."""
    _continuation.recalculate_run_usage_from_extractions(session, run_id)


def _clear_atoms_for_chunk(session: Session, run_id: str, chunk_id: str) -> int:
    """Compatibility entry point for chunk atom cleanup."""
    return _continuation.clear_atoms_for_chunk(session, run_id, chunk_id)


def retry_failed_extractions(session: Session, run_id: str) -> dict:
    """Retry failed extractions and rebuild deterministic outputs."""
    return _continuation.retry_failed_extractions(session, run_id)


def _run_merge_and_final(session: Session, run_id: str) -> None:
    """Compatibility entry point for deterministic output rebuilding."""
    _continuation.run_merge_and_final(session, run_id)


def resume_analysis_run(
    session: Session,
    run_id: str,
    retry_failed: bool = True,
) -> AnalysisRun:
    """Resume missing or failed extraction work without rerunning successes."""
    return _continuation.resume_analysis_run(session, run_id, retry_failed=retry_failed)


def start_retry_failed(run_id: str, engine: Engine | None = None) -> bool:
    """Atomically transition and start one retry executor for a run."""
    engine = _resolve_engine(engine)
    with _EXECUTOR_STATE_LOCK:
        with Session(engine) as session:
            run = session.get(AnalysisRun, run_id)
            if run is None:
                raise ValueError(f"AnalysisRun not found: {run_id}")
            if run.status in (JobStatus.PENDING, JobStatus.RUNNING):
                raise ValueError("Run is already active")
            if run.status not in (JobStatus.PARTIAL_SUCCESS, JobStatus.FAILED):
                raise ValueError("Run has no failed extractions to retry")
            failed = session.exec(
                select(LocalExtraction)
                .where(LocalExtraction.run_id == run_id)
                .where(LocalExtraction.status == "failed")
            ).first()
            if failed is None:
                raise ValueError("No failed extractions found to retry")
            if not _executor_is_available(run):
                return False
            run.status = JobStatus.RUNNING
            run.error_message = None
            run.finished_at = None
            session.add(run)
            session.commit()
            return _launch_registered_executor(
                run,
                _execute_retry,
                (),
                engine,
                name_prefix="analysis-retry",
            )


def start_resume(
    run_id: str,
    retry_failed: bool = True,
    engine: Engine | None = None,
) -> bool:
    """Atomically transition and start one resume executor for a run."""
    engine = _resolve_engine(engine)
    with _EXECUTOR_STATE_LOCK:
        with Session(engine) as session:
            run = session.get(AnalysisRun, run_id)
            if run is None:
                raise ValueError(f"AnalysisRun not found: {run_id}")
            if run.status in (JobStatus.PENDING, JobStatus.RUNNING):
                raise ValueError("Run is already active")
            if run.status == JobStatus.CANCELLED:
                raise ValueError("Cannot resume a cancelled run")
            if run.status == JobStatus.SUCCEEDED:
                raise ValueError("Run is already complete")
            if not _executor_is_available(run):
                return False
            run.status = JobStatus.RUNNING
            run.error_message = None
            run.finished_at = None
            session.add(run)
            session.commit()
            return _launch_registered_executor(
                run,
                _execute_resume,
                (retry_failed,),
                engine,
                name_prefix="analysis-resume",
            )


def _execute_retry(run_id: str, engine: Engine | None = None) -> None:
    engine = _resolve_engine(engine)
    try:
        with Session(engine) as session:
            retry_failed_extractions(session, run_id)
    except Exception as exc:
        _fail_run(run_id, engine, str(exc))


def _execute_resume(
    run_id: str,
    retry_failed: bool,
    engine: Engine | None = None,
) -> None:
    engine = _resolve_engine(engine)
    try:
        with Session(engine) as session:
            resume_analysis_run(session, run_id, retry_failed=retry_failed)
    except Exception as exc:
        _fail_run(run_id, engine, str(exc))


def _resolve_engine(engine: Engine | None = None) -> Engine:
    if engine is not None:
        return engine
    from db import engine as db_engine

    return db_engine


def _executor_is_available(run: AnalysisRun) -> bool:
    active_run_id = _ACTIVE_EXECUTORS_BY_TOPIC.get(run.topic_id)
    return run.id not in _ACTIVE_EXECUTOR_RUNS and active_run_id is None


def _launch_registered_executor(
    run: AnalysisRun,
    target: Callable[..., None],
    target_args: tuple[Any, ...],
    engine: Engine,
    *,
    name_prefix: str,
) -> bool:
    if not _executor_is_available(run):
        return False
    _ACTIVE_EXECUTOR_RUNS.add(run.id)
    _ACTIVE_EXECUTORS_BY_TOPIC[run.topic_id] = run.id
    thread = threading.Thread(
        target=_run_registered_executor,
        args=(run.topic_id, run.id, target, target_args, engine),
        name=f"{name_prefix}-{run.id[:8]}",
        daemon=True,
    )
    try:
        thread.start()
    except Exception as exc:
        _release_executor(run.topic_id, run.id)
        _fail_run(run.id, engine, f"Failed to start analysis executor: {exc}")
        raise
    return True


def _run_registered_executor(
    topic_id: str,
    run_id: str,
    target: Callable[..., None],
    target_args: tuple[Any, ...],
    engine: Engine,
) -> None:
    try:
        target(run_id, *target_args, engine=engine)
    finally:
        _release_executor(topic_id, run_id)


def _release_executor(topic_id: str, run_id: str) -> None:
    with _EXECUTOR_STATE_LOCK:
        _ACTIVE_EXECUTOR_RUNS.discard(run_id)
        if _ACTIVE_EXECUTORS_BY_TOPIC.get(topic_id) == run_id:
            del _ACTIVE_EXECUTORS_BY_TOPIC[topic_id]
