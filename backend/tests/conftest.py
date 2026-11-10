from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_session, upgrade_schema
from app.entities.users import verification
from app.main import create_app


@pytest_asyncio.fixture
async def database() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(upgrade_schema)

    try:
        yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def client(database) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        async with database() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as test_client:
        yield test_client


@pytest.fixture
def sent_verifications(monkeypatch) -> dict[str, str]:
    sent: dict[str, str] = {}

    async def deliver(email: str, token: str) -> None:
        sent[email] = token

    monkeypatch.setattr(verification, "send_verification_email", deliver)
    return sent


@pytest.fixture
def register_verified(client, sent_verifications):
    async def register(email: str) -> dict[str, str]:
        pending = await client.post("/api/v1/auth/register", json={"email": email})
        assert pending.status_code == 202
        verified = await client.post("/api/v1/auth/verify-email", json={
            "token": sent_verifications[email], "password": "password123",
        })
        assert verified.status_code == 200
        return {"Authorization": f"Bearer {verified.json()['token']}"}

    return register
