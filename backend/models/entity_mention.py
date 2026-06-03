from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel


class EntityMention(SQLModel, table=True):
    __tablename__ = "entity_mention"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    topic_id: str = Field(foreign_key="topic.id", index=True)
    global_entity_id: str = Field(foreign_key="global_entity.id", index=True)
    work_id: str = Field(foreign_key="work.id", index=True)
    source_type: str
    source_id: str
    chunk_id: str | None = Field(default=None, index=True)
    chapter_id: str | None = None
    surface_text: str = ""
    evidence_text: str | None = None
    confidence: float = 0.0
    metadata_json: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
