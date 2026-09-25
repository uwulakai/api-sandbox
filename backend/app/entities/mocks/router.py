from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependency import CurrentUser
from app.core.database import get_session
from app.core.types import MockDesiredStatus
from app.entities.models import Mock, MockEndpoint
from app.entities.mocks.schemas import (
    EndpointCreate,
    EndpointPublic,
    EndpointUpdate,
    MockCreate,
    MockPublic,
    MockUpdate,
)
from app.entities.mocks.service import (
    create_endpoint,
    create_mock,
    get_endpoint,
    get_owned_mock,
    mock_public_url,
    update_endpoint,
    update_mock,
    touch_mock,
)


router = APIRouter(prefix="/mocks", tags=["Mocks"])


def to_mock_public(mock: Mock) -> MockPublic:
    return MockPublic(
        **mock.model_dump(),
        public_url=mock_public_url(mock.id),
    )


@router.post("", response_model=MockPublic, status_code=status.HTTP_201_CREATED)
async def create_mock_route(
    payload: MockCreate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> MockPublic:
    mock = await create_mock(session, current_user, payload)
    return to_mock_public(mock)


@router.get("", response_model=list[MockPublic])
async def list_mocks(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> list[MockPublic]:
    result = await session.execute(
        select(Mock)
        .where(Mock.owner_id == current_user.id, Mock.deletion_requested.is_(False))
        .order_by(Mock.created_at.desc())
    )
    return [to_mock_public(mock) for mock in result.scalars().all()]


@router.get("/{mock_id}", response_model=MockPublic)
async def get_mock_route(
    mock_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> MockPublic:
    mock = await get_owned_mock(session, current_user, mock_id)
    return to_mock_public(mock)


@router.patch("/{mock_id}", response_model=MockPublic)
async def update_mock_route(
    mock_id: str,
    payload: MockUpdate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> MockPublic:
    mock = await get_owned_mock(session, current_user, mock_id)
    mock = await update_mock(session, mock, payload)
    return to_mock_public(mock)


@router.delete("/{mock_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mock_route(
    mock_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> Response:
    mock = await get_owned_mock(session, current_user, mock_id)
    mock.deletion_requested = True
    mock.desired_status = MockDesiredStatus.STOPPED
    touch_mock(mock)
    session.add(mock)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{mock_id}/start", response_model=MockPublic)
async def start_mock(
    mock_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> MockPublic:
    mock = await get_owned_mock(session, current_user, mock_id)
    mock.desired_status = MockDesiredStatus.RUNNING
    touch_mock(mock)
    await session.commit()
    await session.refresh(mock)
    return to_mock_public(mock)


@router.post("/{mock_id}/stop", response_model=MockPublic)
async def stop_mock(
    mock_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> MockPublic:
    mock = await get_owned_mock(session, current_user, mock_id)
    mock.desired_status = MockDesiredStatus.STOPPED
    touch_mock(mock)
    await session.commit()
    await session.refresh(mock)
    return to_mock_public(mock)


@router.post("/{mock_id}/restart", response_model=MockPublic)
async def restart_mock(
    mock_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> MockPublic:
    mock = await get_owned_mock(session, current_user, mock_id)
    mock.desired_status = MockDesiredStatus.RUNNING
    touch_mock(mock)
    await session.commit()
    await session.refresh(mock)
    return to_mock_public(mock)


@router.post("/{mock_id}/endpoints", response_model=EndpointPublic, status_code=status.HTTP_201_CREATED)
async def create_endpoint_route(
    mock_id: str,
    payload: EndpointCreate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> EndpointPublic:
    mock = await get_owned_mock(session, current_user, mock_id)
    return await create_endpoint(session, mock, payload)


@router.get("/{mock_id}/endpoints", response_model=list[EndpointPublic])
async def list_endpoints(
    mock_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> list[EndpointPublic]:
    mock = await get_owned_mock(session, current_user, mock_id)
    result = await session.execute(
        select(MockEndpoint)
        .where(MockEndpoint.mock_id == mock.id)
        .order_by(MockEndpoint.created_at)
    )
    return list(result.scalars().all())


@router.get("/{mock_id}/endpoints/{endpoint_id}", response_model=EndpointPublic)
async def get_endpoint_route(
    mock_id: str,
    endpoint_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> EndpointPublic:
    mock = await get_owned_mock(session, current_user, mock_id)
    return await get_endpoint(session, mock, endpoint_id)


@router.patch("/{mock_id}/endpoints/{endpoint_id}", response_model=EndpointPublic)
async def update_endpoint_route(
    mock_id: str,
    endpoint_id: str,
    payload: EndpointUpdate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> EndpointPublic:
    mock = await get_owned_mock(session, current_user, mock_id)
    endpoint = await get_endpoint(session, mock, endpoint_id)
    return await update_endpoint(session, mock, endpoint, payload)


@router.delete("/{mock_id}/endpoints/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_endpoint_route(
    mock_id: str,
    endpoint_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> Response:
    mock = await get_owned_mock(session, current_user, mock_id)
    endpoint = await get_endpoint(session, mock, endpoint_id)
    await session.delete(endpoint)
    touch_mock(mock)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
