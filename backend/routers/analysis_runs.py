"""v0.2 AnalysisRun API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Session, select

from db import get_session
from models.analysis_run import AnalysisRun
from models.topic import Topic
from services import analysis_run_service

topic_router = APIRouter(prefix="/topics/{topic_id}/analysis", tags=["analysis_runs"])
run_router = APIRouter(prefix="/analysis/runs", tags=["analysis_runs"])

VALID_MODES = {"preview", "range", "full", "incremental"}


class CreateRunRequest(BaseModel):
    mode: str = "preview"
    requested_types: list[str] | None = None
    limit_chunks: int | None = None
    chunk_index_start: int | None = None
    chunk_index_end: int | None = None
    chapter_index_start: int | None = None
    chapter_index_end: int | None = None
    force: bool = False
    start_immediately: bool = True

    @field_validator("mode")
    @classmethod
    def check_mode(cls, v: str) -> str:
        if v not in VALID_MODES:
            raise ValueError(f"Invalid mode '{v}'. Must be: preview, range, full, incremental")
        return v

    @field_validator("limit_chunks")
    @classmethod
    def check_limit_chunks(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("limit_chunks must be > 0")
        return v

    @field_validator("chunk_index_start")
    @classmethod
    def check_range_start(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("chunk_index_start must not be negative")
        return v

    @field_validator("chunk_index_end")
    @classmethod
    def check_range_end(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("chunk_index_end must not be negative")
        return v


def _check_topic(topic_id: str, session: Session) -> Topic:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@topic_router.post("/runs", status_code=201)
def create_run(
    topic_id: str,
    body: CreateRunRequest,
    session: Session = Depends(get_session),
) -> dict:
    _check_topic(topic_id, session)

    try:
        run = analysis_run_service.create_analysis_run(
            session,
            topic_id,
            mode=body.mode,
            requested_types=body.requested_types,
            limit_chunks=body.limit_chunks,
            chunk_index_start=body.chunk_index_start,
            chunk_index_end=body.chunk_index_end,
            chapter_index_start=body.chapter_index_start,
            chapter_index_end=body.chapter_index_end,
            force=body.force,
        )
    except ValueError as e:
        msg = str(e)
        # 409 for state conflicts (no provider, not parsed, etc.)
        conflict_keywords = (
            "no provider",
            "no chunks",
            "not parsed",
            "parse document",
            "already running",
        )
        if any(kw in msg.lower() for kw in conflict_keywords):
            raise HTTPException(status_code=409, detail=msg)
        # 422 for invalid input (mode, range, body)
        raise HTTPException(status_code=422, detail=msg)

    if body.start_immediately:
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
                "merge_succeeded": r.merge_succeeded,
                "merge_failed": r.merge_failed,
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


@run_router.post("/{run_id}/retry-failed")
def retry_failed_chunks(run_id: str, session: Session = Depends(get_session)) -> dict:
    from models.local_extraction import LocalExtraction

    run = session.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="AnalysisRun not found")
    if run.status in ("pending", "running"):
        raise HTTPException(status_code=409, detail="Run is already active")
    if run.status not in ("partial_success", "failed"):
        raise HTTPException(status_code=409, detail="Run has no failed extractions to retry")

    failed_exts = session.exec(
        select(LocalExtraction)
        .where(LocalExtraction.run_id == run_id)
        .where(LocalExtraction.status == "failed")
    ).all()
    if not failed_exts:
        raise HTTPException(status_code=409, detail="No failed extractions found to retry")

    run.status = "running"
    session.add(run)
    session.commit()

    analysis_run_service.start_retry_failed(run_id)
    return {
        "run": {"id": run.id, "status": run.status},
        "message": "Retry started in background",
    }


@run_router.post("/{run_id}/resume")
def resume_run(
    run_id: str,
    retry_failed: bool = True,
    session: Session = Depends(get_session),
) -> dict:
    run = session.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="AnalysisRun not found")
    if run.status in ("pending", "running"):
        raise HTTPException(status_code=409, detail="Run is already active")
    if run.status == "cancelled":
        raise HTTPException(status_code=409, detail="Cannot resume a cancelled run")

    run.status = "running"
    session.add(run)
    session.commit()

    analysis_run_service.start_resume(run_id, retry_failed=retry_failed)
    return {
        "run": {"id": run.id, "status": run.status},
        "message": f"Resume started in background (retry_failed={retry_failed})",
    }
