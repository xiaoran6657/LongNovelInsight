from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel

from models.enums import JobStatus, JobType

JOB_TYPES = [JobType.PARSE, JobType.ANALYSIS]
JOB_STATUSES = [s for s in JobStatus]


class Job(SQLModel, table=True):
    __tablename__ = "job"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    topic_id: str = Field(foreign_key="topic.id", index=True)
    job_type: str
    status: str = JobStatus.PENDING
    progress_current: int = 0
    progress_total: int = 0
    progress_failed: int = 0
    current_type: str | None = None
    message: str | None = None
    error_message: str | None = None
    metadata_json: str = "{}"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JobRead(SQLModel):
    id: str
    topic_id: str
    job_type: str
    status: str
    progress_current: int
    progress_total: int
    progress_failed: int
    current_type: str | None
    message: str | None
    error_message: str | None
    job_metadata: dict | None = None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_db(cls, obj: "Job") -> "JobRead":
        import json

        meta = None
        try:
            meta = json.loads(obj.metadata_json) if obj.metadata_json else None
        except (json.JSONDecodeError, TypeError):
            pass
        return cls(
            id=obj.id,
            topic_id=obj.topic_id,
            job_type=obj.job_type,
            status=obj.status,
            progress_current=obj.progress_current,
            progress_total=obj.progress_total,
            progress_failed=obj.progress_failed,
            current_type=obj.current_type,
            message=obj.message,
            error_message=obj.error_message,
            job_metadata=meta,
            started_at=obj.started_at,
            finished_at=obj.finished_at,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )
