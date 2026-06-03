from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel


class Document(SQLModel, table=True):
    __tablename__ = "document"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    topic_id: str = Field(foreign_key="topic.id", unique=True)
    work_id: str | None = Field(default=None, foreign_key="work.id")
    original_filename: str
    stored_filename: str = "original.txt"
    file_type: str = "txt"
    content_type: str | None = None
    encoding: str = "utf-8"
    file_size_bytes: int = 0
    char_count: int = 0
    storage_path: str = ""
    metadata_json: str | None = None
    status: str = "uploaded"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DocumentRead(SQLModel):
    id: str
    topic_id: str
    work_id: str | None = None
    original_filename: str
    stored_filename: str
    file_type: str
    content_type: str | None
    encoding: str
    file_size_bytes: int
    char_count: int
    storage_path: str
    metadata_json: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
