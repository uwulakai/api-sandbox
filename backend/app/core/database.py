from collections.abc import AsyncIterator
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.config import settings


logger = logging.getLogger("api_sandbox.database")


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
            logger.exception("Database session failed; rolling back transaction")
            await session.rollback()
            raise


async def initialize_database() -> None:
    # Temporary bootstrap for the first vertical slice. This will be replaced by
    # a versioned Alembic migration before production deployment.
    from app.entities.models import Mock, MockEndpoint, Session, User  # noqa: F401

    logger.info("Database initialization started")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)
    except Exception:
        logger.exception("Database initialization failed")
        raise
    logger.info("Database initialization completed")
