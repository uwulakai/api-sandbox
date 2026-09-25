from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.core.database import get_session
from app.entities.models import Mock, MockEndpoint, Session, User  # noqa: F401
from app.main import create_app


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as test_client:
        yield test_client

    await engine.dispose()
