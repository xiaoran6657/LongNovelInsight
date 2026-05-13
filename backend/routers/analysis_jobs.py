from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from db import get_session
from models.chunk import Chunk
from models.document import Document
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


@topic_router.post("/jobs", status_code=201)
def create_analysis_job(
    topic_id: str,
    job_type: str = "ANALYSIS_ALL",
    session: Session = Depends(get_session),
) -> dict:
    _check_topic(topic_id, session)
    _check_document(topic_id, session)
    _check_chunks(topic_id, session)

    if job_type not in JOB_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid job_type: {job_type}")

    job = job_service.create_analysis_job(topic_id, job_type, session)
    items = job_service.create_default_analysis_items(job.id, session)
    session.commit()

    job = job_service.run_stub_analysis_job(job.id, session)
    items = job_service.get_job_items(job.id, session)

    return {
        "job": JobRead.model_validate(job).model_dump(),
        "items": [JobItemRead.model_validate(i).model_dump() for i in items],
    }


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
    completed_types = set()
    if latest_job and latest_job.status == "SUCCEEDED":
        items = job_service.get_job_items(latest_job.id, session)
        completed_types = {i.item_type for i in items if i.status == "SUCCEEDED"}

    return {
        "topic_id": topic_id,
        "has_jobs": len(jobs) > 0,
        "latest_job": JobRead.model_validate(latest_job).model_dump() if latest_job else None,
        "analysis_types_completed": sorted(completed_types),
    }


@job_router.get("/{job_id}")
def get_job_detail(job_id: str, session: Session = Depends(get_session)) -> dict:
    job = job_service.get_job(job_id, session)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    items = job_service.get_job_items(job_id, session)
    return {
        "job": JobRead.model_validate(job).model_dump(),
        "items": [JobItemRead.model_validate(i).model_dump() for i in items],
    }


@job_router.post("/{job_id}/cancel")
def cancel_job(job_id: str, session: Session = Depends(get_session)) -> dict:
    job = job_service.cancel_job(job_id, session)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    items = job_service.get_job_items(job_id, session)
    return {
        "job": JobRead.model_validate(job).model_dump(),
        "items": [JobItemRead.model_validate(i).model_dump() for i in items],
    }
