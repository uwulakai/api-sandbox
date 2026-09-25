from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.types import MockRuntimeStatus
from app.entities.models import Mock, MockEndpoint, User
from app.entities.mocks.schemas import EndpointCreate, EndpointUpdate, MockCreate, MockUpdate


def mock_public_url(mock_id: str) -> str:
    return f"{settings.mock_public_base_url.rstrip('/')}/{mock_id}"


async def get_owned_mock(session: AsyncSession, user: User, mock_id: str) -> Mock:
    mock = await session.scalar(
        select(Mock).where(
            Mock.id == mock_id,
            Mock.owner_id == user.id,
            Mock.deletion_requested.is_(False),
        )
    )
    if mock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mock not found")
    return mock


def touch_mock(mock: Mock) -> None:
    mock.config_version += 1
    mock.runtime_status = MockRuntimeStatus.PENDING
    mock.last_error = None
    mock.updated_at = datetime.now(timezone.utc)


async def create_mock(session: AsyncSession, user: User, payload: MockCreate) -> Mock:
    mock = Mock(
        owner_id=user.id,
        name=payload.name,
        description=payload.description,
        desired_status=payload.desired_status,
    )
    session.add(mock)
    await session.commit()
    await session.refresh(mock)
    return mock


async def update_mock(session: AsyncSession, mock: Mock, payload: MockUpdate) -> Mock:
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(mock, field, value)
    if changes:
        touch_mock(mock)
    session.add(mock)
    await session.commit()
    await session.refresh(mock)
    return mock


async def create_endpoint(
    session: AsyncSession,
    mock: Mock,
    payload: EndpointCreate,
) -> MockEndpoint:
    duplicate = await session.scalar(
        select(MockEndpoint).where(
            MockEndpoint.mock_id == mock.id,
            MockEndpoint.method == payload.method,
            MockEndpoint.path == payload.path,
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An endpoint with the same method and path already exists",
        )

    endpoint = MockEndpoint(mock_id=mock.id, **payload.model_dump())
    session.add(endpoint)
    touch_mock(mock)
    await session.commit()
    await session.refresh(endpoint)
    return endpoint


async def get_endpoint(session: AsyncSession, mock: Mock, endpoint_id: str) -> MockEndpoint:
    endpoint = await session.scalar(
        select(MockEndpoint).where(
            MockEndpoint.id == endpoint_id,
            MockEndpoint.mock_id == mock.id,
        )
    )
    if endpoint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")
    return endpoint


async def update_endpoint(
    session: AsyncSession,
    mock: Mock,
    endpoint: MockEndpoint,
    payload: EndpointUpdate,
) -> MockEndpoint:
    changes = payload.model_dump(exclude_unset=True)
    method = changes.get("method", endpoint.method)
    path = changes.get("path", endpoint.path)
    duplicate = await session.scalar(
        select(MockEndpoint).where(
            MockEndpoint.mock_id == mock.id,
            MockEndpoint.method == method,
            MockEndpoint.path == path,
            MockEndpoint.id != endpoint.id,
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An endpoint with the same method and path already exists",
        )

    for field, value in changes.items():
        setattr(endpoint, field, value)
    touch_mock(mock)
    session.add(endpoint)
    await session.commit()
    await session.refresh(endpoint)
    return endpoint
