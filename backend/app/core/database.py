from collections.abc import AsyncIterator
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


logger = logging.getLogger("api_sandbox.database")


engine = create_async_engine(settings.database_url, echo=settings.debug, hide_parameters=True)
session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        try:
            yield session
        except Exception as exc:
            await session.rollback()
            if not isinstance(exc, HTTPException):
                logger.exception("Database session failed; rolling back transaction")
            raise


def upgrade_schema(connection: Connection) -> None:
    if connection.dialect.name == "postgresql":
        connection.execute(text("SELECT pg_advisory_xact_lock(2133765491)"))
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    config.attributes["connection"] = connection
    command.upgrade(config, "head")


async def initialize_database() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(upgrade_schema)
