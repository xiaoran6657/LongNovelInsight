from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from db import get_session
from models.chunk import Chunk
from models.document import Document
from models.enums import JobStatus
from models.job import JOB_TYPES, JobRead
from models.job_item import JobItemRead
from models.topic import Topic
from services import job_service

topic_router = APIRouter(prefix="/topics/{topic_id}/analysis", tags=["analysis_jobs"])
job_router = APIRouter(prefix="/analysis/jobs", tags=["analysis_jobs"])


def _check_topic(topic_id: str, session: Session) -> Topic:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


def _check_document(topic_id: str, session: Session) -> Document:
    doc = session.exec(select(Document).where(Document.topic_id == topic_id)).first()
    if doc is None:
        raise HTTPException(status_code=409, detail="No document uploaded")
    return doc


def _check_chunks(topic_id: str, session: Session) -> None:
    chunk = session.exec(select(Chunk).where(Chunk.topic_id == topic_id).limit(1)).first()
    if chunk is None:
        raise HTTPException(
            status_code=409, detail="Document must be parsed before running analysis"
        )


@topic_router.post("/jobs", status_code=202)
def create_analysis_job(
    topic_id: str,
    job_type: str = "analysis",
    session: Session = Depends(get_session),
) -> dict:
    import threading

    _check_topic(topic_id, session)
    _check_document(topic_id, session)
    _check_chunks(topic_id, session)

    if job_type not in JOB_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid job_type: {job_type}")

    job = job_service.create_analysis_job(topic_id, job_type, session)
    items = job_service.create_default_analysis_items(job.id, session)
    session.commit()

    job_id = job.id
    thread = threading.Thread(
        target=_run_job_in_background,
        args=(job_id,),
        name=f"analysis-job-{job_id[:8]}",
        daemon=True,
    )
    thread.start()

    return {
        "job": JobRead.from_db(job).model_dump(),
        "items": [JobItemRead.model_validate(i).model_dump() for i in items],
        "message": "Job created and started in background",
    }


def _run_job_in_background(job_id: str) -> None:
    from db import engine
    from models.job import Job

    try:
        with Session(engine) as session:
            job = session.get(Job, job_id)
            if job is None:
                return
            job_service.run_analysis_job(job_id, session)
    except Exception:
        pass


@topic_router.get("/jobs")
def list_analysis_jobs(topic_id: str, session: Session = Depends(get_session)) -> dict:
    _check_topic(topic_id, session)
    jobs = job_service.get_topic_jobs(topic_id, session)
    return {"jobs": [JobRead.model_validate(j).model_dump() for j in jobs]}


@topic_router.get("/status")
def get_analysis_status(topic_id: str, session: Session = Depends(get_session)) -> dict:
    _check_topic(topic_id, session)
    jobs = job_service.get_topic_jobs(topic_id, session)

    latest_job = jobs[0] if jobs else None
    completed_types: set[str] = set()
    if latest_job:
        items = job_service.get_job_items(latest_job.id, session)
        completed_types = {i.item_type for i in items if i.status in (JobStatus.SUCCEEDED,)}

    # Output counts by type (exclude v2 merge_* intermediates)
    from models.analysis_output import AnalysisOutput

    outputs = session.exec(select(AnalysisOutput).where(AnalysisOutput.topic_id == topic_id)).all()
    final_outputs = [o for o in outputs if not o.output_type.startswith("merge_")]
    output_counts: dict[str, int] = {}
    for o in final_outputs:
        output_counts[o.output_type] = output_counts.get(o.output_type, 0) + 1

    # Latest v2 AnalysisRun summary
    from models.analysis_run import AnalysisRun

    latest_run = session.exec(
        select(AnalysisRun)
        .where(AnalysisRun.topic_id == topic_id)
        .order_by(AnalysisRun.created_at.desc())
        .limit(1)
    ).first()
    latest_v2_run = None
    if latest_run:
        latest_v2_run = {
            "id": latest_run.id,
            "mode": latest_run.mode,
            "status": latest_run.status,
            "progress_current": latest_run.progress_current,
            "progress_total": latest_run.progress_total,
            "extraction_succeeded": latest_run.extraction_succeeded,
            "extraction_failed": latest_run.extraction_failed,
            "merge_succeeded": latest_run.merge_succeeded,
            "merge_failed": latest_run.merge_failed,
            "final_succeeded": latest_run.final_succeeded,
            "final_failed": latest_run.final_failed,
            "final_skipped": latest_run.final_skipped,
            "total_tokens": latest_run.total_tokens,
            "model_used": latest_run.model_used,
            "started_at": latest_run.started_at.isoformat() if latest_run.started_at else None,
            "finished_at": latest_run.finished_at.isoformat() if latest_run.finished_at else None,
            "created_at": latest_run.created_at.isoformat() if latest_run.created_at else None,
        }

    return {
        "topic_id": topic_id,
        "has_jobs": len(jobs) > 0,
        "has_outputs": len(final_outputs) > 0,
        "latest_job": JobRead.from_db(latest_job).model_dump() if latest_job else None,
        "analysis_types_completed": sorted(completed_types),
        "output_counts_by_type": output_counts,
        "latest_v2_run": latest_v2_run,
        "v2_available": True,
    }


@job_router.get("/{job_id}")
def get_job_detail(job_id: str, session: Session = Depends(get_session)) -> dict:
    job = job_service.get_job(job_id, session)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    items = job_service.get_job_items(job_id, session)
    return {
        "job": JobRead.from_db(job).model_dump(),
        "items": [JobItemRead.model_validate(i).model_dump() for i in items],
    }


@job_router.post("/{job_id}/cancel")
def cancel_job(job_id: str, session: Session = Depends(get_session)) -> dict:
    job = job_service.cancel_job(job_id, session)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    items = job_service.get_job_items(job_id, session)
    return {
        "job": JobRead.from_db(job).model_dump(),
        "items": [JobItemRead.model_validate(i).model_dump() for i in items],
    }
