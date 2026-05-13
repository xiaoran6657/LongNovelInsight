from datetime import datetime, timezone

from sqlmodel import Session, select

from models.job import JOB_TYPES, Job
from models.job_item import ITEM_TYPES, JobItem


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_analysis_job(topic_id: str, job_type: str, session: Session) -> Job:
    if job_type not in JOB_TYPES:
        raise ValueError(f"Invalid job_type: {job_type}")

    job = Job(
        topic_id=topic_id,
        job_type=job_type,
        status="PENDING",
        progress_current=0,
        progress_total=len(ITEM_TYPES),
    )
    session.add(job)
    session.flush()
    return job


def create_default_analysis_items(job_id: str, session: Session) -> list[JobItem]:
    items = []
    for item_type in ITEM_TYPES:
        item = JobItem(job_id=job_id, item_type=item_type, status="PENDING")
        session.add(item)
        items.append(item)
    session.flush()
    return items


def get_topic_jobs(topic_id: str, session: Session) -> list[Job]:
    return list(
        session.exec(
            select(Job).where(Job.topic_id == topic_id).order_by(Job.created_at.desc())
        ).all()
    )


def get_job(job_id: str, session: Session) -> Job | None:
    return session.get(Job, job_id)


def get_job_items(job_id: str, session: Session) -> list[JobItem]:
    return list(
        session.exec(
            select(JobItem).where(JobItem.job_id == job_id).order_by(JobItem.created_at)
        ).all()
    )


def cancel_job(job_id: str, session: Session) -> Job | None:
    job = session.get(Job, job_id)
    if job is None:
        return None
    if job.status in ("PENDING", "RUNNING"):
        job.status = "CANCELLED"
        job.finished_at = _now()
        job.message = "Job cancelled by user"
        session.add(job)

        items = get_job_items(job_id, session)
        for item in items:
            if item.status in ("PENDING", "RUNNING"):
                item.status = "CANCELLED"
                item.message = "Cancelled"
                session.add(item)

        session.commit()
        session.refresh(job)
    return job


def run_stub_analysis_job(job_id: str, session: Session) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise ValueError("Job not found")

    if job.status == "CANCELLED":
        return job

    now = _now()
    job.status = "RUNNING"
    job.started_at = now
    job.message = "Analysis started"
    session.add(job)
    session.flush()

    items = get_job_items(job_id, session)
    for i, item in enumerate(items):
        if job.status == "CANCELLED":
            return job
        item.status = "RUNNING"
        session.add(item)
        session.flush()

        # Stub: immediately succeed
        item.status = "SUCCEEDED"
        item.progress_current = 1
        item.progress_total = 1
        item.message = f"Stub: {item.item_type} completed"
        session.add(item)
        session.flush()

        job.progress_current = i + 1

    job.status = "SUCCEEDED"
    job.finished_at = _now()
    job.message = "Analysis complete (stub)"
    session.add(job)
    session.commit()
    session.refresh(job)
    return job
