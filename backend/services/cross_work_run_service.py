"""Cross-work run orchestration — execute entity/graph/timeline builders."""

import json
import threading
import time
from datetime import datetime, timezone

from sqlmodel import Session, select

from models.cross_work_run import CrossWorkRun


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_cross_work_run(
    session: Session,
    topic_id: str,
    mode: str = "full",
    work_ids: list[str] | None = None,
) -> CrossWorkRun:
    """Create a CrossWorkRun row and persist it."""
    run = CrossWorkRun(
        topic_id=topic_id,
        status="pending",
        mode=mode,
        stats_json="{}",
        warnings_json="[]",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def execute_cross_work_run(run_id: str, engine=None) -> None:
    """Execute a cross-work run synchronously. Updates status, stats, warnings."""
    if engine is None:
        from db import engine as db_engine

        engine = db_engine

    try:
        _execute_impl(run_id, engine)
    except Exception as e:
        _fail_run(run_id, engine, str(e))


def _execute_impl(run_id: str, engine) -> None:
    # Use a single session for the entire execution to avoid SQLite lock contention
    with Session(engine) as session:
        run = session.get(CrossWorkRun, run_id)
        if run is None:
            return
        run.status = "running"
        run.started_at = _now()
        session.add(run)
        session.commit()
        topic_id = run.topic_id
        mode = run.mode

    # Builders run with their own sessions, but we must ensure all outer
    # sessions are closed before calling them (SQLite single-writer constraint).
    # The session above is committed and closed (context manager exit).

    all_warnings: list[str] = []
    stats: dict = {}

    # Entities
    if mode in ("full", "entities_only"):
        start = time.monotonic()
        try:
            from services.cross_work_entity_service import build_entity_registry

            with Session(engine) as s:
                result = build_entity_registry(topic_id, s)
            stats["entities"] = {
                "entity_count": result.get("entity_count", 0),
                "mention_count": result.get("mention_count", 0),
                "duration_seconds": round(time.monotonic() - start, 3),
            }
            all_warnings.extend(result.get("warnings", []))
        except Exception as e:
            stats["entities"] = {
                "error": str(e)[:500],
                "duration_seconds": round(time.monotonic() - start, 3),
            }
            all_warnings.append(f"Entity build failed: {e}")

    # Graph
    if mode in ("full", "graph_only"):
        start = time.monotonic()
        try:
            from services.cross_work_graph_service import build_character_graph

            with Session(engine) as s:
                result = build_character_graph(topic_id, s)
            stats["graph"] = {
                "node_count": len(result.get("nodes", [])),
                "edge_count": len(result.get("edges", [])),
                "duration_seconds": round(time.monotonic() - start, 3),
            }
        except Exception as e:
            stats["graph"] = {
                "error": str(e)[:500],
                "duration_seconds": round(time.monotonic() - start, 3),
            }
            all_warnings.append(f"Graph build failed: {e}")

    # Timeline
    if mode in ("full", "timeline_only"):
        start = time.monotonic()
        try:
            from services.cross_work_timeline_service import build_timeline

            with Session(engine) as s:
                result = build_timeline(topic_id, s)
            stats["timeline"] = {
                "item_count": result.get("item_count", 0),
                "duration_seconds": round(time.monotonic() - start, 3),
            }
        except Exception as e:
            stats["timeline"] = {
                "error": str(e)[:500],
                "duration_seconds": round(time.monotonic() - start, 3),
            }
            all_warnings.append(f"Timeline build failed: {e}")

    # Finalize with a fresh session (previous builder sessions are closed)
    with Session(engine) as session:
        run = session.get(CrossWorkRun, run_id)
        if run is None:
            return
        run.status = "succeeded"
        run.completed_at = _now()
        run.stats_json = json.dumps(stats, ensure_ascii=False)
        run.warnings_json = json.dumps(all_warnings[:20], ensure_ascii=False)
        session.add(run)
        session.commit()


def _fail_run(run_id: str, engine, error: str) -> None:
    try:
        with Session(engine) as session:
            run = session.get(CrossWorkRun, run_id)
            if run and run.status not in ("succeeded", "cancelled"):
                run.status = "failed"
                run.error = error[:1000]
                run.completed_at = _now()
                session.add(run)
                session.commit()
    except Exception:
        pass


def get_cross_work_run_status(session: Session, run_id: str) -> dict | None:
    run = session.get(CrossWorkRun, run_id)
    if run is None:
        return None

    return {
        "id": run.id,
        "topic_id": run.topic_id,
        "status": run.status,
        "mode": run.mode,
        "stats": json.loads(run.stats_json) if run.stats_json else {},
        "warnings": json.loads(run.warnings_json) if run.warnings_json else [],
        "error": run.error,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


def list_cross_work_runs(
    session: Session, topic_id: str, limit: int = 20, offset: int = 0
) -> tuple[list[CrossWorkRun], int]:
    base = select(CrossWorkRun).where(CrossWorkRun.topic_id == topic_id)
    total = len(session.exec(base).all())
    runs = list(
        session.exec(
            base.order_by(CrossWorkRun.created_at.desc()).offset(offset).limit(limit)
        ).all()
    )
    return runs, total


def start_cross_work_run(run_id: str) -> None:
    """Start a background thread to execute a cross-work run."""
    thread = threading.Thread(
        target=execute_cross_work_run,
        args=(run_id,),
        name=f"cross-work-run-{run_id[:8]}",
        daemon=True,
    )
    thread.start()
