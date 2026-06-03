from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel


class GraphSnapshot(SQLModel, table=True):
    __tablename__ = "graph_snapshot"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    topic_id: str = Field(foreign_key="topic.id", index=True)
    graph_type: str
    version: int = 1
    scope_json: str = "{}"
    nodes_json: str = "[]"
    edges_json: str = "[]"
    stats_json: str = "{}"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
