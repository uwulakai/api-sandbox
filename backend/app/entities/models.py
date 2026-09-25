from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.types import MockDesiredStatus, MockRuntimeStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True, max_length=320)
    password_hash: str = Field(max_length=255)
    is_active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Session(SQLModel, table=True):
    __tablename__ = "sessions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    token_hash: str = Field(index=True, unique=True, max_length=64)
    expires_at: datetime
    last_seen_at: datetime = Field(default_factory=utc_now)
    created_at: datetime = Field(default_factory=utc_now)


class Mock(SQLModel, table=True):
    __tablename__ = "mocks"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    owner_id: int = Field(foreign_key="users.id", index=True)
    name: str = Field(max_length=120)
    description: str | None = Field(default=None, max_length=500)
    desired_status: MockDesiredStatus = Field(default=MockDesiredStatus.RUNNING)
    runtime_status: MockRuntimeStatus = Field(default=MockRuntimeStatus.PENDING)
    deletion_requested: bool = False
    container_id: str | None = Field(default=None, max_length=128)
    config_version: int = Field(default=1, ge=1)
    last_error: str | None = Field(default=None, max_length=2000)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class MockEndpoint(SQLModel, table=True):
    __tablename__ = "mock_endpoints"
    __table_args__ = (
        UniqueConstraint("mock_id", "method", "path", name="uq_mock_endpoint_method_path"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    mock_id: str = Field(foreign_key="mocks.id", index=True)
    method: str = Field(max_length=10, index=True)
    path: str = Field(max_length=2048)
    status_code: int = Field(default=200, ge=100, le=599)
    response_headers: dict[str, str] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    response_body: Any = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    delay_ms: int = Field(default=0, ge=0, le=60_000)
    enabled: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
