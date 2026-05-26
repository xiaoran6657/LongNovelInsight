from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel


class Chapter(SQLModel, table=True):
    __tablename__ = "chapter"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    topic_id: str = Field(foreign_key="topic.id", index=True)
    document_id: str = Field(foreign_key="document.id")
    chapter_index: int
    title: str
    start_char: int
    end_char: int
    char_count: int = 0
    source_href: str | None = None
    nav_order: int | None = None
    metadata_json: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChapterRead(SQLModel):
    id: str
    topic_id: str
    document_id: str
    chapter_index: int
    title: str
    start_char: int
    end_char: int
    char_count: int
    source_href: str | None
    nav_order: int | None
    metadata_json: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
