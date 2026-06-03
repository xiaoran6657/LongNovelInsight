from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel


class GlobalEntity(SQLModel, table=True):
    __tablename__ = "global_entity"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    topic_id: str = Field(foreign_key="topic.id", index=True)
    entity_type: str = Field(default="unknown")
    canonical_name: str
    aliases_json: str = "[]"
    work_ids_json: str = "[]"
    mention_count: int = 0
    evidence_count: int = 0
    confidence: float = 0.0
    merge_strategy: str = "exact"
    metadata_json: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
