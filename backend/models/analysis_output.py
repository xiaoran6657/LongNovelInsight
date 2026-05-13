import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel

from models.enums import AnalysisType

OUTPUT_TYPES = [t for t in AnalysisType]


class AnalysisOutput(SQLModel, table=True):
    __tablename__ = "analysis_output"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    topic_id: str = Field(foreign_key="topic.id", index=True)
    job_id: str | None = Field(default=None, foreign_key="job.id")
    output_type: str
    title: str
    content_json: str
    source_chunk_ids: str
    evidence_quotes: str
    confidence: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AnalysisOutputCreate(SQLModel):
    topic_id: str
    job_id: str | None = None
    output_type: str
    title: str
    content_json: str
    source_chunk_ids: str
    evidence_quotes: str
    confidence: float = 0.0


class AnalysisOutputRead(SQLModel):
    id: str
    topic_id: str
    job_id: str | None
    output_type: str
    title: str
    content_json: dict | list | None
    source_chunk_ids: list[str]
    evidence_quotes: list[str]
    confidence: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_json(cls, obj: AnalysisOutput) -> "AnalysisOutputRead":
        return cls(
            id=obj.id,
            topic_id=obj.topic_id,
            job_id=obj.job_id,
            output_type=obj.output_type,
            title=obj.title,
            content_json=_safe_json_parse(obj.content_json),
            source_chunk_ids=_safe_json_parse(obj.source_chunk_ids),
            evidence_quotes=_safe_json_parse(obj.evidence_quotes),
            confidence=obj.confidence,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


def _safe_json_parse(value: str) -> dict | list | None:
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None
