from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel

ITEM_TYPES = [
    "OVERVIEW",
    "CHARACTERS",
    "RELATIONS",
    "EVENTS",
    "CAUSALITY",
    "THEMES",
]


class JobItem(SQLModel, table=True):
    __tablename__ = "job_item"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    job_id: str = Field(foreign_key="job.id", index=True)
    item_type: str
    status: str = "PENDING"
    progress_current: int = 0
    progress_total: int = 1
    message: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JobItemRead(SQLModel):
    id: str
    job_id: str
    item_type: str
    status: str
    progress_current: int
    progress_total: int
    message: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
