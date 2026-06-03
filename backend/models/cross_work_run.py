from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel


class CrossWorkRun(SQLModel, table=True):
    __tablename__ = "cross_work_run"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    topic_id: str = Field(foreign_key="topic.id", index=True)
    status: str = "pending"
    mode: str = "full"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    stats_json: str = "{}"
    warnings_json: str = "[]"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
