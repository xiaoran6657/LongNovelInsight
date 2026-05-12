from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel


class Chunk(SQLModel, table=True):
    __tablename__ = "chunk"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    topic_id: str = Field(foreign_key="topic.id", index=True)
    document_id: str = Field(foreign_key="document.id")
    chapter_id: str | None = Field(default=None, foreign_key="chapter.id")
    chunk_index: int
    chapter_index: int | None = None
    text: str = ""
    start_char: int
    end_char: int
    char_count: int = 0
    estimated_tokens: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChunkRead(SQLModel):
    id: str
    topic_id: str
    document_id: str
    chapter_id: str | None
    chunk_index: int
    chapter_index: int | None
    text: str
    start_char: int
    end_char: int
    char_count: int
    estimated_tokens: int
    created_at: datetime

    model_config = {"from_attributes": True}
