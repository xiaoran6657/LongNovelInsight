import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel

from models.enums import AnalysisMode, JobStatus


class AnalysisRun(SQLModel, table=True):
    __tablename__ = "analysis_run"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    topic_id: str = Field(foreign_key="topic.id", index=True)
    job_id: str | None = Field(default=None, foreign_key="job.id")
    mode: str = Field(default=AnalysisMode.PREVIEW)
    status: str = Field(default=JobStatus.PENDING)

    requested_types_json: str = Field(default="[]")
    chunk_selection_json: str = Field(default="{}")
    effective_config_json: str = Field(default="{}")

    progress_current: int = 0
    progress_total: int = 0
    extraction_total: int = 0
    extraction_succeeded: int = 0
    extraction_failed: int = 0
    merge_total: int = 0
    merge_succeeded: int = 0
    merge_failed: int = 0

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model_used: str | None = None
    error_message: str | None = None
    metadata_json: str = Field(default="{}")

    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def set_requested_types(self, types: list[str]) -> None:
        self.requested_types_json = json.dumps(types, ensure_ascii=False)

    def get_requested_types(self) -> list[str]:
        try:
            return json.loads(self.requested_types_json)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_chunk_selection(self, data: dict) -> None:
        self.chunk_selection_json = json.dumps(data, ensure_ascii=False)

    def get_chunk_selection(self) -> dict:
        try:
            return json.loads(self.chunk_selection_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_effective_config(self, data: dict) -> None:
        self.effective_config_json = json.dumps(data, ensure_ascii=False)

    def get_effective_config(self) -> dict:
        try:
            return json.loads(self.effective_config_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_metadata(self, data: dict) -> None:
        self.metadata_json = json.dumps(data, ensure_ascii=False)

    def get_metadata(self) -> dict:
        try:
            return json.loads(self.metadata_json)
        except (json.JSONDecodeError, TypeError):
            return {}
