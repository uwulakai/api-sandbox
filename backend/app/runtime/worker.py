import asyncio
import logging

from sqlalchemy import select

from app.config import settings
from app.core.database import session_factory
from app.core.types import MockDesiredStatus, MockRuntimeStatus
from app.entities.models import Mock, MockEndpoint
from app.runtime.docker_manager import DockerRuntimeManager


logger = logging.getLogger(__name__)


async def reconcile_once(manager: DockerRuntimeManager) -> None:
    async with session_factory() as session:
        result = await session.execute(
            select(Mock).where(Mock.runtime_status == MockRuntimeStatus.PENDING)
        )
        mocks = list(result.scalars().all())

    for mock in mocks:
        async with session_factory() as session:
            current = await session.get(Mock, mock.id)
            if current is None or current.runtime_status != MockRuntimeStatus.PENDING:
                continue

            current.runtime_status = (
                MockRuntimeStatus.STOPPING
                if current.desired_status == MockDesiredStatus.STOPPED
                else MockRuntimeStatus.STARTING
            )
            await session.commit()

            endpoints_result = await session.execute(
                select(MockEndpoint).where(MockEndpoint.mock_id == current.id)
            )
            endpoints = list(endpoints_result.scalars().all())

        try:
            container_id = await asyncio.to_thread(manager.reconcile, current, endpoints)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Mock runtime reconciliation failed: mock_id=%s", current.id)
            async with session_factory() as session:
                failed = await session.get(Mock, current.id)
                if failed is not None:
                    failed.runtime_status = MockRuntimeStatus.ERROR
                    failed.last_error = str(exc)[:2000]
                    await session.commit()
            continue

        async with session_factory() as session:
            completed = await session.get(Mock, current.id)
            if completed is None:
                continue
            completed.container_id = container_id
            completed.runtime_status = (
                MockRuntimeStatus.STOPPED
                if completed.desired_status == MockDesiredStatus.STOPPED
                else MockRuntimeStatus.RUNNING
            )
            completed.last_error = None
            if completed.deletion_requested:
                endpoints_to_delete = await session.execute(
                    select(MockEndpoint).where(MockEndpoint.mock_id == completed.id)
                )
                for endpoint in endpoints_to_delete.scalars().all():
                    await session.delete(endpoint)
                await session.delete(completed)
            await session.commit()


async def run_worker() -> None:
    manager = DockerRuntimeManager()
    while True:
        await reconcile_once(manager)
        await asyncio.sleep(settings.runtime_worker_poll_seconds)


if __name__ == "__main__":
    asyncio.run(run_worker())
