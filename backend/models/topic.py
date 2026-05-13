from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel

from models.enums import TopicStatus


class Topic(SQLModel, table=True):
    __tablename__ = "topic"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str
    description: str | None = None
    provider_id: str | None = Field(default=None, foreign_key="model_provider.id", index=True)
    storage_bytes: int = 0
    status: str = TopicStatus.CREATED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TopicCreate(SQLModel):
    name: str
    description: str | None = None
    provider_id: str | None = None


class TopicRead(SQLModel):
    id: str
    name: str
    description: str | None = None
    provider_id: str | None = None
    storage_bytes: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
