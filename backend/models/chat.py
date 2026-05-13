import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel


class ChatSession(SQLModel, table=True):
    __tablename__ = "chat_session"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    topic_id: str = Field(foreign_key="topic.id", index=True)
    title: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_message"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    session_id: str = Field(foreign_key="chat_session.id", index=True)
    role: str  # "user" | "assistant" | "system"
    content: str
    evidence_json: str | None = None
    uncertainty: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatSessionCreate(SQLModel):
    title: str


class ChatSessionRead(SQLModel):
    id: str
    topic_id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageCreate(SQLModel):
    content: str

    @classmethod
    def parse_and_validate(cls, data: dict) -> "ChatMessageCreate":
        content = data.get("content")
        if content is None:
            raise ValueError("content is required")
        if not isinstance(content, str):
            raise ValueError("content must be a string")
        trimmed = content.strip()
        if not trimmed:
            raise ValueError("content must not be empty")
        if len(trimmed) > 20000:
            raise ValueError("content must not exceed 20000 characters")
        return cls(content=trimmed)


class ChatMessageRead(SQLModel):
    id: str
    session_id: str
    role: str
    content: str
    evidence_json: str | None = None
    uncertainty: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatAnswerRead(SQLModel):
    id: str
    session_id: str
    role: str
    content: str
    evidence_json: dict | list | None = None
    uncertainty: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_message(cls, msg: ChatMessage) -> "ChatAnswerRead":
        return cls(
            id=msg.id,
            session_id=msg.session_id,
            role=msg.role,
            content=msg.content,
            evidence_json=_safe_json(msg.evidence_json),
            uncertainty=msg.uncertainty,
            created_at=msg.created_at,
        )


def _safe_json(value: str | None) -> dict | list | None:
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None
