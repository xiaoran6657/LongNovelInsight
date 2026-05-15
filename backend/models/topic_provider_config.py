from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from sqlmodel import Field, SQLModel


class TopicProviderConfig(SQLModel, table=True):
    __tablename__ = "topic_provider_config"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    topic_id: str = Field(foreign_key="topic.id", unique=True, index=True)
    provider_id: str | None = Field(default=None, foreign_key="model_provider.id")

    base_url_override: str | None = None
    model_name_override: str | None = None
    context_window_override: int | None = None
    max_output_tokens_override: int | None = None
    temperature_override: float | None = None

    thinking_mode_override: str | None = None  # "enabled" | "disabled" | "provider_default"
    reasoning_effort_override: str | None = None  # "high" | "max"

    analysis_parallelism_override: int | None = None
    recommended_profile: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TopicProviderConfigCreate(SQLModel):
    provider_id: str | None = None
    base_url_override: str | None = None
    model_name_override: str | None = None
    context_window_override: int | None = None
    max_output_tokens_override: int | None = None
    temperature_override: float | None = None
    thinking_mode_override: Literal["enabled", "disabled", "provider_default"] | None = None  # noqa: E501
    reasoning_effort_override: Literal["high", "max"] | None = None
    analysis_parallelism_override: int | None = None
    recommended_profile: str | None = None


class TopicProviderConfigRead(SQLModel):
    id: str
    topic_id: str
    provider_id: str | None
    base_url_override: str | None
    model_name_override: str | None
    context_window_override: int | None
    max_output_tokens_override: int | None
    temperature_override: float | None
    thinking_mode_override: str | None
    reasoning_effort_override: str | None
    analysis_parallelism_override: int | None
    recommended_profile: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EffectiveProviderConfig(SQLModel):
    provider_id: str | None = None
    provider_name: str | None = None
    provider_key: str | None = None
    base_url: str | None = None
    model_name: str | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    temperature: float | None = None
    thinking_mode: str = "disabled"
    reasoning_effort: str | None = None
    analysis_parallelism: int = 3
    supports_json_output: bool = True
    supports_thinking: bool = False
    is_ready: bool = False
    missing_fields: list[str] = []
    warnings: list[str] = []
