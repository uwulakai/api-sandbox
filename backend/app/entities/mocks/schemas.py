from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.types import MockDesiredStatus, MockRuntimeStatus


def normalize_path(value: str) -> str:
    if not value.startswith("/"):
        value = f"/{value}"
    if len(value) > 1:
        value = value.rstrip("/")
    return value or "/"


class MockCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    desired_status: MockDesiredStatus = MockDesiredStatus.RUNNING


class MockUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    desired_status: MockDesiredStatus | None = None


class MockPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    desired_status: MockDesiredStatus
    runtime_status: MockRuntimeStatus
    deletion_requested: bool
    config_version: int
    public_url: str
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class EndpointCreate(BaseModel):
    method: str = Field(min_length=1, max_length=10)
    path: str = Field(min_length=1, max_length=2048)
    status_code: int = Field(default=200, ge=100, le=599)
    response_headers: dict[str, str] = Field(default_factory=dict)
    response_body: Any = Field(default_factory=dict)
    delay_ms: int = Field(default=0, ge=0, le=60_000)
    enabled: bool = True

    @field_validator("method")
    @classmethod
    def validate_method(cls, value: str) -> str:
        value = value.upper()
        allowed = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
        if value not in allowed:
            raise ValueError("Unsupported HTTP method")
        return value

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return normalize_path(value)


class EndpointUpdate(BaseModel):
    method: str | None = Field(default=None, min_length=1, max_length=10)
    path: str | None = Field(default=None, min_length=1, max_length=2048)
    status_code: int | None = Field(default=None, ge=100, le=599)
    response_headers: dict[str, str] | None = None
    response_body: Any | None = None
    delay_ms: int | None = Field(default=None, ge=0, le=60_000)
    enabled: bool | None = None

    @field_validator("method")
    @classmethod
    def validate_method(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return EndpointCreate.validate_method(value)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str | None) -> str | None:
        return normalize_path(value) if value is not None else value


class EndpointPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    mock_id: str
    method: str
    path: str
    status_code: int
    response_headers: dict[str, str]
    response_body: Any
    delay_ms: int
    enabled: bool
