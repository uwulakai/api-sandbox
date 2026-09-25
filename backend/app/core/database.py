from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.config import settings


engine = create_async_engine(settings.database_url, echo=settings.debug)
session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def initialize_database() -> None:
    # Temporary bootstrap for the first vertical slice. This will be replaced by
    # a versioned Alembic migration before production deployment.
    from app.entities.models import Mock, MockEndpoint, Session, User  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
