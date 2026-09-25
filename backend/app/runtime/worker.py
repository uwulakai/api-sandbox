import asyncio
import logging
from time import monotonic

from sqlalchemy import select

from app.config import settings
from app.core.database import session_factory
from app.core.types import MockDesiredStatus, MockRuntimeStatus
from app.entities.models import Mock, MockEndpoint
from app.runtime.docker_manager import DockerRuntimeManager


logger = logging.getLogger("api_sandbox.runtime_worker")


async def reconcile_once(manager: DockerRuntimeManager) -> None:
    async with session_factory() as session:
        result = await session.execute(
            select(Mock).where(Mock.runtime_status == MockRuntimeStatus.PENDING)
        )
        mocks = list(result.scalars().all())

    if mocks:
        logger.info(
            "Pending mocks found: count=%s mock_ids=%s",
            len(mocks),
            ",".join(mock.id for mock in mocks),
        )

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
            logger.info(
                "Mock reconciliation started: mock_id=%s desired_status=%s",
                current.id,
                current.desired_status.value,
            )

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
        logger.info(
            "Mock reconciliation completed: mock_id=%s runtime_status=%s",
            current.id,
            "stopped" if current.desired_status == MockDesiredStatus.STOPPED else "running",
        )


async def run_worker() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    manager = DockerRuntimeManager()
    logger.info(
        "Runtime worker started: poll_seconds=%s image=%s network=%s",
        settings.runtime_worker_poll_seconds,
        settings.mock_runtime_image,
        settings.mock_network_name,
    )
    last_heartbeat = monotonic()
    while True:
        try:
            await reconcile_once(manager)
        except Exception:  # noqa: BLE001
            # A transient database/Docker error must not terminate the worker.
            # The next polling cycle will retry reconciliation.
            logger.exception("Runtime reconciliation cycle failed")
        if monotonic() - last_heartbeat >= 30:
            logger.info("Runtime worker heartbeat: alive=true")
            last_heartbeat = monotonic()
        await asyncio.sleep(settings.runtime_worker_poll_seconds)


if __name__ == "__main__":
    asyncio.run(run_worker())
