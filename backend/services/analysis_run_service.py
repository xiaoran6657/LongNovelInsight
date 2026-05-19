"""v0.2 AnalysisRun orchestration: create, start, parallel extraction, cancel."""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from sqlmodel import Session, select

from models.analysis_run import AnalysisRun
from models.enums import AnalysisMode, JobStatus
from models.local_extraction import LocalExtraction
from services import atom_normalizer as _atom_normalizer
from services import local_extraction_worker as _extraction_worker


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Create & Start ──


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
) -> AnalysisRun:
    """Create an AnalysisRun and persist it."""
    from services.analysis_selection_service import (
        select_chunks_for_analysis,
        validate_analysis_mode,
    )
    from services.provider_config_service import get_effective_config

    validate_analysis_mode(mode)

    # Validate chunks exist
    from models.chunk import Chunk
    chunk = session.exec(
        select(Chunk).where(Chunk.topic_id == topic_id).limit(1)
    ).first()
    if chunk is None:
        raise ValueError("No chunks found; parse document first")

    # Select chunks
    selected, selection_info = select_chunks_for_analysis(
        session, topic_id, mode,
        limit_chunks=limit_chunks,
        range_start=chunk_index_start,
        range_end=chunk_index_end,
        chapter_start=chapter_index_start,
        chapter_end=chapter_index_end,
    )

    # Resolve effective config
    effective = get_effective_config(session, topic_id)
    if not effective or not effective.is_ready:
        raise ValueError("No provider configured for this topic")

    types = requested_types or ["overview", "characters", "relations", "events", "causality", "themes"]

    run = AnalysisRun(
        topic_id=topic_id,
        mode=mode,
        status=JobStatus.PENDING,
        extraction_total=len(selected),
        merge_total=len(types),
        progress_total=len(selected) + len(types) + len(types),
        model_used=effective.model_name,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )
    run.set_requested_types(types)
    run.set_chunk_selection(selection_info)
    run.set_effective_config({
        "model_name": effective.model_name or "",
        "base_url": effective.base_url or "",
        "temperature": effective.temperature,
        "max_output_tokens": effective.max_output_tokens or 3072,
        "thinking_mode": effective.thinking_mode,
        "analysis_parallelism": effective.analysis_parallelism,
    })
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def start_analysis_run(run_id: str) -> None:
    """Start a background thread to execute the analysis run."""
    thread = threading.Thread(
        target=_execute_run,
        args=(run_id,),
        name=f"analysis-run-{run_id[:8]}",
        daemon=True,
    )
    thread.start()


# ── Execution ──


def _execute_run(run_id: str, engine=None) -> None:
    """Background thread: run local_extraction for all selected chunks in parallel.

    engine can be injected for testing. Defaults to db.engine.
    """
    if engine is None:
        from db import engine as db_engine
        engine = db_engine

    # Open a fresh session for this thread
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        if run is None or run.status in (JobStatus.CANCELLED,):
            return

        run.status = JobStatus.RUNNING
        run.started_at = _now()
        session.add(run)
        session.commit()

        config = run.get_effective_config()
        parallelism = min(max(config.get("analysis_parallelism", 3), 1), 6)
        model_name = config.get("model_name", "")
        base_url = config.get("base_url", "")
        # api_key comes from provider
        api_key = _resolve_api_key(session, run.topic_id)
        temperature = config.get("temperature") or 0.1
        max_tokens = config.get("max_output_tokens") or 3072
        thinking_mode = config.get("thinking_mode", "disabled")

        # Load selected chunks
        from models.chunk import Chunk
        selection = run.get_chunk_selection()
        all_chunks = session.exec(
            select(Chunk)
            .where(Chunk.topic_id == run.topic_id)
            .order_by(Chunk.chapter_index, Chunk.chunk_index)
        ).all()

        if "selected" in selection and selection["selected"] > 0:
            selected = all_chunks[:selection["selected"]]
        else:
            selected = all_chunks

        # Extract chapter titles for metadata
        from models.chapter import Chapter
        chapters = session.exec(
            select(Chapter).where(Chapter.topic_id == run.topic_id)
        ).all()
        chapter_map = {ch.chapter_index: ch.title for ch in chapters}

        # ── Parallel extraction ──
        succeeded = 0
        failed = 0
        total_tokens = 0

        with ThreadPoolExecutor(max_workers=parallelism, thread_name_prefix="v2-extract") as executor:
            futures = {}
            for chunk in selected:
                future = executor.submit(
                    _extraction_worker.run_local_extraction_for_chunk,
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
                    chapter_title=chapter_map.get(chunk.chapter_index),
                )
                futures[future] = chunk.id

            for future in as_completed(futures):
                chunk_id = futures[future]
                try:
                    result = future.result()
                except Exception as e:
                    failed += 1
                    _save_extraction(session, run_id, run.topic_id, chunk_id, ok=False, error=str(e))
                    continue

                _save_extraction(
                    session, run_id, run.topic_id, chunk_id,
                    ok=result.ok,
                    content_json=result.content_json,
                    parsed_json=result.parsed_json,
                    error=result.error,
                    prompt_tokens=result.prompt_tokens,
                    completion_tokens=result.completion_tokens,
                    total_tokens=result.total_tokens,
                    model_used=result.model_used,
                    retry_count=result.retry_count,
                )
                if result.ok:
                    succeeded += 1
                else:
                    failed += 1
                total_tokens += result.total_tokens

                # Update progress
                run = session.get(AnalysisRun, run_id)
                if run is None or run.status == JobStatus.CANCELLED:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                run.extraction_succeeded = succeeded
                run.extraction_failed = failed
                run.total_tokens = total_tokens
                run.progress_current = succeeded + failed
                session.add(run)
                session.commit()

        # Finalize status
        run = session.get(AnalysisRun, run_id)
        if run and run.status != JobStatus.CANCELLED:
            if succeeded > 0 and failed == 0:
                run.status = JobStatus.SUCCEEDED
            elif succeeded > 0:
                run.status = JobStatus.PARTIAL_SUCCESS
            else:
                run.status = JobStatus.FAILED
            run.finished_at = _now()
            session.add(run)
            session.commit()


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
) -> None:
    """Write a LocalExtraction row and, if successful, normalize atoms."""
    ext = LocalExtraction(
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
    )
    session.add(ext)
    session.flush()

    if ok and content_json:
        _atom_normalizer.normalize_local_extraction(
            extraction_id=ext.id,
            run_id=run_id,
            topic_id=topic_id,
            chunk_id=chunk_id,
            content_json_str=content_json,
            session=session,
        )


def _resolve_api_key(session: Session, topic_id: str) -> str:
    """Get the API key for the topic's bound provider."""
    from models.model_provider import ModelProvider
    from models.topic import Topic

    topic = session.get(Topic, topic_id)
    if topic and topic.provider_id:
        provider = session.get(ModelProvider, topic.provider_id)
        if provider:
            return provider.api_key
    # Fallback to default provider
    provider = session.exec(
        select(ModelProvider).where(ModelProvider.is_default == True)  # noqa: E712
    ).first()
    if provider:
        return provider.api_key
    raise ValueError("No provider configured")


# ── Status & List & Cancel ──


def get_analysis_run_status(session: Session, run_id: str) -> dict | None:
    """Return run status with extraction summary."""
    run = session.get(AnalysisRun, run_id)
    if run is None:
        return None

    extractions = session.exec(
        select(LocalExtraction).where(LocalExtraction.run_id == run_id)
    ).all()

    return {
        "run": {
            "id": run.id,
            "topic_id": run.topic_id,
            "mode": run.mode,
            "status": run.status,
            "progress_current": run.progress_current,
            "progress_total": run.progress_total,
            "extraction_succeeded": run.extraction_succeeded,
            "extraction_failed": run.extraction_failed,
            "total_tokens": run.total_tokens,
            "model_used": run.model_used,
            "error_message": run.error_message,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        },
        "extractions": [
            {
                "id": e.id,
                "chunk_id": e.chunk_id,
                "status": e.status,
                "attempt_count": e.attempt_count,
                "error_message": e.error_message,
            }
            for e in extractions
        ],
    }


def list_analysis_runs(session: Session, topic_id: str) -> list[AnalysisRun]:
    """List all analysis runs for a topic, most recent first."""
    return list(
        session.exec(
            select(AnalysisRun)
            .where(AnalysisRun.topic_id == topic_id)
            .order_by(AnalysisRun.created_at.desc())
        ).all()
    )


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
