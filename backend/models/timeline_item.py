from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel


class TimelineItem(SQLModel, table=True):
    __tablename__ = "timeline_item"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    topic_id: str = Field(foreign_key="topic.id", index=True)
    work_id: str | None = Field(default=None, foreign_key="work.id", index=True)
    event_atom_id: str | None = None
    title: str
    summary: str | None = None
    sequence_index: float | None = None
    time_label: str | None = None
    participants_json: str = "[]"
    locations_json: str = "[]"
    causes_json: str = "[]"
    effects_json: str = "[]"
    evidence_json: str = "[]"
    confidence: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
