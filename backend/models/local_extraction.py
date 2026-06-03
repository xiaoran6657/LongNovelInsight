from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel


class LocalExtraction(SQLModel, table=True):
    __tablename__ = "local_extraction"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    run_id: str = Field(foreign_key="analysis_run.id", index=True)
    topic_id: str = Field(foreign_key="topic.id", index=True)
    chunk_id: str = Field(foreign_key="chunk.id", index=True)
    status: str = Field(default="pending")

    attempt_count: int = 0
    content_json: str | None = None
    source_chunk_ids: str = "[]"
    evidence_quotes: str = "[]"
    confidence: float = 0.0

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    reasoning_tokens: int = 0
    prompt_cache_hit_tokens: int = 0
    prompt_cache_miss_tokens: int = 0
    usage_unavailable_attempts: int = 0
    attempt_usage_json: str | None = None
    model_used: str | None = None
    error_message: str | None = None

    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
