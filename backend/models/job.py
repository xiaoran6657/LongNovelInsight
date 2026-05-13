from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel

JOB_TYPES = [
    "ANALYSIS_OVERVIEW",
    "ANALYSIS_CHARACTERS",
    "ANALYSIS_RELATIONS",
    "ANALYSIS_EVENTS",
    "ANALYSIS_CAUSALITY",
    "ANALYSIS_THEMES",
    "ANALYSIS_ALL",
]

JOB_STATUSES = ["PENDING", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"]


class Job(SQLModel, table=True):
    __tablename__ = "job"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    topic_id: str = Field(foreign_key="topic.id", index=True)
    job_type: str
    status: str = "PENDING"
    progress_current: int = 0
    progress_total: int = 0
    message: str | None = None
    error_message: str | None = None
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
    message: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
