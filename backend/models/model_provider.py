from datetime import datetime, timezone
from uuid import uuid4

from pydantic import model_validator
from sqlmodel import Field, SQLModel


def mask_api_key(key: str) -> str:
    if len(key) <= 8:
        return "***"
    return key[:3] + "..." + key[-4:]


class ModelProvider(SQLModel, table=True):
    __tablename__ = "model_provider"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str = Field(unique=True)
    provider_type: str
    base_url: str
    api_key: str
    model_name: str
    context_window: int = 1_000_000
    max_output_tokens: int = 8192
    temperature: float = 0.2
    is_default: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def masked_api_key(self) -> str:
        return mask_api_key(self.api_key)


class ModelProviderCreate(SQLModel):
    name: str
    provider_type: str
    base_url: str
    api_key: str
    model_name: str
    context_window: int = 1_000_000
    max_output_tokens: int = 8192
    temperature: float = 0.2
    is_default: bool = False

    @model_validator(mode="after")
    def _validate_fields(self) -> "ModelProviderCreate":
        if not self.name.strip():
            raise ValueError("name must not be empty")
        if self.context_window <= 0:
            raise ValueError("context_window must be > 0")
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be > 0")
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError("temperature must be between 0.0 and 2.0")
        return self


class ModelProviderRead(SQLModel):
    id: str
    name: str
    provider_type: str
    base_url: str
    model_name: str
    context_window: int
    max_output_tokens: int
    temperature: float
    is_default: bool
    masked_api_key: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModelProviderUpdate(SQLModel):
    name: str | None = None
    provider_type: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model_name: str | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    temperature: float | None = None
    is_default: bool | None = None
