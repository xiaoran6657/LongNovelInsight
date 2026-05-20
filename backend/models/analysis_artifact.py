from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel


class AnalysisArtifact(SQLModel, table=True):
    __tablename__ = "analysis_artifact"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    topic_id: str = Field(foreign_key="topic.id", index=True)
    run_id: str | None = Field(default=None, foreign_key="analysis_run.id")
    artifact_type: str  # local_extraction | merged_analysis | final_output | debug
    owner_table: str  # local_extraction | analysis_output
    owner_id: str  # UUID of the owning row
    storage_path: str  # relative path within data/
    size_bytes: int = 0
    sha256: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
