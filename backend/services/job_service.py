from datetime import datetime, timezone

from sqlmodel import Session, select

from models.enums import JobStatus
from models.job import JOB_TYPES, Job
from models.job_item import ITEM_TYPES, JobItem
from services import analysis_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_analysis_job(topic_id: str, job_type: str, session: Session) -> Job:
    if job_type not in JOB_TYPES:
        raise ValueError(f"Invalid job_type: {job_type}")

    job = Job(
        topic_id=topic_id,
        job_type=job_type,
        status=JobStatus.PENDING,
        progress_current=0,
        progress_total=len(ITEM_TYPES),
    )
    session.add(job)
    session.flush()
    return job


def create_default_analysis_items(job_id: str, session: Session) -> list[JobItem]:
    items = []
    for item_type in ITEM_TYPES:
        item = JobItem(job_id=job_id, item_type=item_type, status=JobStatus.PENDING)
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
    if job.status in (JobStatus.PENDING, JobStatus.RUNNING):
        job.status = JobStatus.CANCELLED
        job.finished_at = _now()
        job.message = "Job cancelled by user"
        session.add(job)

        items = get_job_items(job_id, session)
        for item in items:
            if item.status in (JobStatus.PENDING, JobStatus.RUNNING):
                item.status = JobStatus.CANCELLED
                item.message = "Cancelled"
                session.add(item)

        session.commit()
        session.refresh(job)
    return job


def run_analysis_job(job_id: str, session: Session) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise ValueError("Job not found")

    if job.status == JobStatus.CANCELLED:
        return job

    now = _now()
    job.status = JobStatus.RUNNING
    job.started_at = now
    session.add(job)
    session.commit()

    items = get_job_items(job_id, session)

    # Parse jobs don't call LLM — just mark items succeeded immediately
    if job.job_type == "parse":
        job.message = "Parse job is synchronous; no LLM calls"
        for i, item in enumerate(items):
            item.status = JobStatus.SUCCEEDED
            item.message = f"{item.item_type} stub"
            session.add(item)
            job.progress_current = i + 1
        job.status = JobStatus.SUCCEEDED
        job.finished_at = _now()
        session.add(job)
        session.commit()
        session.refresh(job)
        return job

    # Analysis job: run real analysis per item
    job.message = "Analysis started"
    session.add(job)
    session.commit()

    failed_count = 0
    for i, item in enumerate(items):
        session.refresh(job)
        if job.status == JobStatus.CANCELLED:
            job.message = "Job was cancelled during execution"
            session.add(job)
            session.commit()
            return job

        item.status = JobStatus.RUNNING
        session.add(item)
        session.commit()

        try:
            analysis_service.run_single_analysis_output(
                topic_id=job.topic_id,
                output_type=item.item_type,
                session=session,
                limit_chunks=5,
            )
            item.status = JobStatus.SUCCEEDED
            item.message = f"{item.item_type} completed"
        except Exception as e:
            item.status = JobStatus.FAILED
            safe_msg = str(e)
            item.message = safe_msg[:500]
            item.error_message = safe_msg[:1000]
            failed_count += 1

        session.add(item)
        session.flush()
        job.progress_current = i + 1
        session.add(job)

    if failed_count == 0:
        job.status = JobStatus.SUCCEEDED
        job.message = "Analysis complete"
    else:
        job.status = JobStatus.FAILED
        job.message = f"Analysis complete with {failed_count} failed item(s)"

    job.finished_at = _now()
    session.add(job)
    session.commit()
    session.refresh(job)
    return job
