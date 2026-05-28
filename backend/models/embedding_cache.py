"""Embedding cache for optional semantic rerank (v0.3 Step 10).

SQLite-stored JSON vectors — small-scale only, no ANN index.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel


class EmbeddingCache(SQLModel, table=True):
    __tablename__ = "embedding_cache"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    topic_id: str = Field(foreign_key="topic.id", index=True)
    source_type: str  # chunk | analysis_output | atom
    source_id: str  # chunk_id, output_id, or atom_id
    model_name: str
    vector_json: str  # JSON array of floats
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
