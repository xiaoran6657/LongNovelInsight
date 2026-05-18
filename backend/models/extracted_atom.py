from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel


class ExtractedAtom(SQLModel, table=True):
    __tablename__ = "extracted_atom"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    run_id: str = Field(foreign_key="analysis_run.id", index=True)
    topic_id: str = Field(foreign_key="topic.id", index=True)
    local_extraction_id: str | None = Field(default=None, foreign_key="local_extraction.id")
    chunk_id: str | None = Field(default=None, foreign_key="chunk.id")

    atom_type: str
    stable_id: str
    canonical_name: str | None = None
    title: str | None = None
    summary: str | None = None
    content_json: str = "{}"

    source_chunk_ids: str = "[]"
    evidence_quotes: str = "[]"
    confidence: float = 0.0

    chapter_index: int | None = None
    chunk_index: int | None = None
    order_index: int | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
