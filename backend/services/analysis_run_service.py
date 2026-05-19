"""v0.2 AnalysisRun orchestration: create, start, parallel extraction, merge, cancel."""

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

    chunk = session.exec(select(Chunk).where(Chunk.topic_id == topic_id).limit(1)).first()
    if chunk is None:
        raise ValueError("No chunks found; parse document first")

    # Select chunks
    selected, selection_info = select_chunks_for_analysis(
        session,
        topic_id,
        mode,
        limit_chunks=limit_chunks,
        range_start=chunk_index_start,
        range_end=chunk_index_end,
        chapter_start=chapter_index_start,
        chapter_end=chapter_index_end,
    )

    # Persist selected chunk IDs in selection info
    selection_info["selected_chunk_ids"] = [c.id for c in selected]

    # Resolve effective config
    effective = get_effective_config(session, topic_id)
    if not effective or not effective.is_ready:
        raise ValueError("No provider configured for this topic")

    types = requested_types or [
        "overview",
        "characters",
        "relations",
        "events",
        "causality",
        "themes",
    ]

    # Map requested types to merge types (same names for v0.2)
    merge_requested_types = [
        t
        for t in types
        if t
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
    extraction_total = len(selected)
    merge_total = len(merge_requested_types)
    progress_total = extraction_total + merge_total

    run = AnalysisRun(
        topic_id=topic_id,
        mode=mode,
        status=JobStatus.PENDING,
        extraction_total=extraction_total,
        merge_total=merge_total,
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
    """Background thread: extraction → merge pipeline.

    engine can be injected for testing. Defaults to db.engine.
    """
    if engine is None:
        from db import engine as db_engine

        engine = db_engine

    try:
        _execute_run_impl(run_id, engine)
    except Exception as e:
        _fail_run(run_id, engine, str(e))


def _fail_run(run_id: str, engine, error: str) -> None:
    """Mark a run as failed due to an unhandled exception."""
    try:
        with Session(engine) as session:
            run = session.get(AnalysisRun, run_id)
            if run and run.status not in (JobStatus.SUCCEEDED, JobStatus.CANCELLED):
                # Truncate and mask potential api_keys in error
                safe = error[:500]
                run.status = JobStatus.FAILED
                run.error_message = safe
                run.finished_at = _now()
                session.add(run)
                session.commit()
    except Exception:
        pass  # best-effort failure recording


def _execute_run_impl(run_id: str, engine) -> None:
    from models.chapter import Chapter
    from models.chunk import Chunk

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
        api_key = _resolve_api_key(session, run.topic_id)
        temperature = config.get("temperature") or 0.1
        max_tokens = config.get("max_output_tokens") or 3072
        thinking_mode = config.get("thinking_mode", "disabled")

        # Load selected chunks by persisted IDs
        selection = run.get_chunk_selection()
        selected_chunk_ids = selection.get("selected_chunk_ids", [])
        if not selected_chunk_ids:
            run.status = JobStatus.FAILED
            run.error_message = "No chunks selected"
            run.finished_at = _now()
            session.add(run)
            session.commit()
            return

        # Query chunks by IDs, preserving order
        id_to_chunk = {}
        all_chunks = session.exec(
            select(Chunk).where(Chunk.id.in_(selected_chunk_ids))  # noqa: E711
        ).all()
        for c in all_chunks:
            id_to_chunk[c.id] = c
        selected = [id_to_chunk[cid] for cid in selected_chunk_ids if cid in id_to_chunk]

        if not selected:
            run.status = JobStatus.FAILED
            run.error_message = "No chunks selected"
            run.finished_at = _now()
            session.add(run)
            session.commit()
            return

        # Extract chapter titles for metadata
        chapters = session.exec(select(Chapter).where(Chapter.topic_id == run.topic_id)).all()
        chapter_map = {ch.chapter_index: ch.title for ch in chapters}

    # ── Parallel extraction (outside session to avoid long-lived sessions) ──
    succeeded = 0
    failed = 0
    total_tokens = 0
    failed_chunks: list[dict] = []

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

            # Check cancel before saving
            with Session(engine) as session:
                run = session.get(AnalysisRun, run_id)
                if run is None or run.status == JobStatus.CANCELLED:
                    executor.shutdown(wait=False, cancel_futures=True)
                    return

            try:
                result = future.result()
            except Exception as e:
                failed += 1
                failed_chunks.append({"chunk_id": chunk_id, "error": str(e)[:200]})
                with Session(engine) as session:
                    _save_extraction(
                        session, run_id, run.topic_id, chunk_id, ok=False, error=str(e)
                    )
                continue

            with Session(engine) as session:
                _save_extraction(
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

    # ── Post-extraction: check cancel, then run merge ──
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        if run is None:
            return

        # If cancelled, skip merge
        if run.status == JobStatus.CANCELLED:
            run.finished_at = run.finished_at or _now()
            session.add(run)
            session.commit()
            return

        # Update extraction counters
        run.extraction_succeeded = succeeded
        run.extraction_failed = failed
        run.total_tokens = total_tokens
        run.progress_current = succeeded + failed

        # Determine final status if no merge is possible
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

        # ── Merge stage ──
        requested_types = run.get_requested_types()
        merge_types = [
            t
            for t in requested_types
            if t
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
                for s in merge_summaries
                if s.atom_count >= 0 and not any("Merge failed:" in w for w in s.warnings)
            )
            merge_failed_count = sum(
                1 for s in merge_summaries if any("Merge failed:" in w for w in s.warnings)
            )
            merge_warnings: list[str] = []
            for s in merge_summaries:
                merge_warnings.extend(s.warnings)

            run = session.get(AnalysisRun, run_id)  # refresh
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

        # ── Final status ──
        run = session.get(AnalysisRun, run_id)
        if run and run.status != JobStatus.CANCELLED:
            if succeeded == 0:
                run.status = JobStatus.FAILED
            elif failed == 0 and merge_failed_count == 0:
                run.status = JobStatus.SUCCEEDED
            else:
                run.status = JobStatus.PARTIAL_SUCCESS
            run.finished_at = _now()
            run.set_metadata(
                {
                    "stage": "completed",
                    "failed_chunks": failed_chunks,
                    "merge_summaries": [
                        {"type": s.merge_type, "atoms": s.atom_count, "merged": s.merged_count}
                        for s in merge_summaries
                    ],
                    "warnings": merge_warnings,
                }
            )
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
    """Get the API key for the topic's bound provider.

    Priority: TopicProviderConfig.provider_id > Topic.provider_id > default provider.
    """
    from models.model_provider import ModelProvider
    from models.topic import Topic
    from models.topic_provider_config import TopicProviderConfig

    # 1. Check TopicProviderConfig.provider_id
    tpc = session.exec(
        select(TopicProviderConfig).where(TopicProviderConfig.topic_id == topic_id)
    ).first()
    if tpc and tpc.provider_id:
        provider = session.get(ModelProvider, tpc.provider_id)
        if provider and provider.api_key:
            return provider.api_key

    # 2. Check Topic.provider_id
    topic = session.get(Topic, topic_id)
    if topic and topic.provider_id:
        provider = session.get(ModelProvider, topic.provider_id)
        if provider and provider.api_key:
            return provider.api_key

    # 3. Fallback to default provider
    provider = session.exec(
        select(ModelProvider).where(ModelProvider.is_default == True)  # noqa: E712
    ).first()
    if provider and provider.api_key:
        return provider.api_key

    raise ValueError("No provider configured")


# ── Status & List & Cancel ──


def get_analysis_run_status(session: Session, run_id: str) -> dict | None:
    """Return run status with extraction and merge summary."""
    from models.analysis_output import AnalysisOutput

    run = session.get(AnalysisRun, run_id)
    if run is None:
        return None

    extractions = session.exec(
        select(LocalExtraction).where(LocalExtraction.run_id == run_id)
    ).all()

    merge_outputs = session.exec(
        select(AnalysisOutput).where(AnalysisOutput.run_id == run_id)
    ).all()

    metadata = run.get_metadata()

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
        "merge": {
            "total": run.merge_total or 0,
            "succeeded": run.merge_succeeded or 0,
            "failed": run.merge_failed or 0,
            "outputs": [
                {
                    "id": o.id,
                    "output_type": o.output_type,
                    "title": o.title,
                }
                for o in merge_outputs
            ],
            "warnings": metadata.get("warnings", []),
        },
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
