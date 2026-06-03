from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel

from models.enums import WorkStatus


class Work(SQLModel, table=True):
    __tablename__ = "work"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    topic_id: str = Field(foreign_key="topic.id", index=True)
    title: str
    subtitle: str | None = None
    author: str | None = None
    series_index: int | None = None
    description: str | None = None
    status: str = WorkStatus.EMPTY
    metadata_json: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkCreate(SQLModel):
    title: str
    subtitle: str | None = None
    author: str | None = None
    series_index: int | None = None
    description: str | None = None


class WorkUpdate(SQLModel):
    title: str | None = None
    subtitle: str | None = None
    author: str | None = None
    series_index: int | None = None
    description: str | None = None


class WorkRead(SQLModel):
    id: str
    topic_id: str
    title: str
    subtitle: str | None = None
    author: str | None = None
    series_index: int | None = None
    description: str | None = None
    status: str
    metadata_json: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
