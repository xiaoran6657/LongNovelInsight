from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel


class RetrievalTrace(SQLModel, table=True):
    __tablename__ = "retrieval_trace"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    topic_id: str = Field(foreign_key="topic.id", index=True)
    session_id: str | None = Field(default=None, foreign_key="chat_session.id")
    message_id: str | None = Field(default=None, foreign_key="chat_message.id")
    query: str
    method: str
    results_json: str = "[]"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
