"""v0.2 AnalysisRun API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from db import get_session
from models.topic import Topic
from services import analysis_run_service

topic_router = APIRouter(prefix="/topics/{topic_id}/analysis", tags=["analysis_runs"])
run_router = APIRouter(prefix="/analysis/runs", tags=["analysis_runs"])


def _check_topic(topic_id: str, session: Session) -> Topic:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@topic_router.post("/runs", status_code=201)
def create_run(
    topic_id: str,
    body: dict,
    session: Session = Depends(get_session),
) -> dict:
    _check_topic(topic_id, session)

    try:
        run = analysis_run_service.create_analysis_run(
            session,
            topic_id,
            mode=body.get("mode", "preview"),
            requested_types=body.get("requested_types"),
            limit_chunks=body.get("limit_chunks"),
            chunk_index_start=body.get("chunk_index_start"),
            chunk_index_end=body.get("chunk_index_end"),
            chapter_index_start=body.get("chapter_index_start"),
            chapter_index_end=body.get("chapter_index_end"),
            force=body.get("force", False),
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # Start background execution
    analysis_run_service.start_analysis_run(run.id)

    return {
        "run": {
            "id": run.id,
            "topic_id": run.topic_id,
            "mode": run.mode,
            "status": run.status,
            "progress_total": run.progress_total,
        },
        "status_url": f"/api/analysis/runs/{run.id}",
    }


@topic_router.get("/runs")
def list_runs(
    topic_id: str,
    session: Session = Depends(get_session),
) -> dict:
    _check_topic(topic_id, session)
    runs = analysis_run_service.list_analysis_runs(session, topic_id)
    return {
        "runs": [
            {
                "id": r.id,
                "mode": r.mode,
                "status": r.status,
                "extraction_succeeded": r.extraction_succeeded,
                "extraction_failed": r.extraction_failed,
                "total_tokens": r.total_tokens,
                "model_used": r.model_used,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in runs
        ]
    }


@run_router.get("/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    status = analysis_run_service.get_analysis_run_status(session, run_id)
    if status is None:
        raise HTTPException(status_code=404, detail="AnalysisRun not found")
    return status


@run_router.post("/{run_id}/cancel")
def cancel_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    run = analysis_run_service.cancel_analysis_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="AnalysisRun not found")
    return {
        "run": {
            "id": run.id,
            "status": run.status,
        }
    }
