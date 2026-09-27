import asyncio
import logging
import signal
from time import monotonic

from sqlalchemy import select

from app.config import settings
from app.core.database import session_factory
from app.core.types import MockDesiredStatus, MockRuntimeStatus
from app.entities.models import Mock, MockEndpoint
from app.runtime.docker_manager import DockerRuntimeManager


logger = logging.getLogger("api_sandbox.runtime_worker")


async def prepare_runtime_for_start(manager: DockerRuntimeManager) -> None:
    """Reconcile all platform-owned containers after Compose starts."""
    managed_containers = await asyncio.to_thread(manager.list_managed)

    if managed_containers:
        logger.info(
            "Stopping runtime containers before startup reconciliation: count=%s",
            len(managed_containers),
        )
        await asyncio.gather(
            *(
                asyncio.to_thread(manager.remove_container, container)
                for container in managed_containers
            ),
            return_exceptions=True,
        )

    async with session_factory() as session:
        result = await session.execute(select(Mock))
        mocks = list(result.scalars().all())

        active_mock_ids = {
            mock.id for mock in mocks if not mock.deletion_requested
        }
        for mock in mocks:
            mock.runtime_status = MockRuntimeStatus.PENDING
            mock.container_id = None
            mock.last_error = None
        await session.commit()

    orphan_count = sum(
        1
        for container in managed_containers
        if container.labels.get("com.api-sandbox.mock-id") not in active_mock_ids
    )
    if orphan_count:
        logger.info(
            "Removing orphan mock containers: count=%s",
            orphan_count,
        )

    logger.info(
        "Runtime startup reconciliation prepared: mocks=%s existing_containers=%s orphans=%s",
        len(mocks),
        len(managed_containers),
        orphan_count,
    )


async def shutdown_runtime(manager: DockerRuntimeManager) -> None:
    """Stop and remove every platform-owned runtime container before Compose stops."""
    try:
        managed_containers = await asyncio.to_thread(manager.list_managed)
    except Exception:  # noqa: BLE001
        logger.exception("Unable to list managed containers during worker shutdown")
        return

    logger.info(
        "Runtime worker shutdown started: managed_containers=%s",
        len(managed_containers),
    )
    results = await asyncio.gather(
        *(
            asyncio.to_thread(manager.remove_container, container)
            for container in managed_containers
        ),
        return_exceptions=True,
    )
    failures = [result for result in results if isinstance(result, Exception)]
    if failures:
        for failure in failures:
            logger.error("Managed container cleanup failed: %s", failure)

    try:
        async with session_factory() as session:
            result = await session.execute(select(Mock))
            for mock in result.scalars().all():
                mock.runtime_status = MockRuntimeStatus.STOPPED
                mock.container_id = None
            await session.commit()
    except Exception:  # noqa: BLE001
        # Container cleanup is the important part of shutdown. The next
        # startup reconciliation repairs runtime status if the database is
        # already unavailable during Compose shutdown.
        logger.exception("Unable to persist runtime statuses during shutdown")

    logger.info(
        "Runtime worker shutdown completed: removed=%s failures=%s",
        len(managed_containers) - len(failures),
        len(failures),
    )


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
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for termination_signal in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(termination_signal, stop_event.set)
        except NotImplementedError:
            # Signal handlers are available in the Linux container used by Dokploy.
            pass

    logger.info(
        "Runtime worker started: poll_seconds=%s image=%s network=%s",
        settings.runtime_worker_poll_seconds,
        settings.mock_runtime_image,
        settings.mock_network_name,
    )
    try:
        await prepare_runtime_for_start(manager)
        last_heartbeat = monotonic()
        while not stop_event.is_set():
            try:
                await reconcile_once(manager)
            except Exception:  # noqa: BLE001
                # A transient database/Docker error must not terminate the worker.
                # The next polling cycle will retry reconciliation.
                logger.exception("Runtime reconciliation cycle failed")
            if monotonic() - last_heartbeat >= 30:
                logger.info("Runtime worker heartbeat: alive=true")
                last_heartbeat = monotonic()
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=settings.runtime_worker_poll_seconds,
                )
            except TimeoutError:
                pass
    finally:
        await shutdown_runtime(manager)


if __name__ == "__main__":
    asyncio.run(run_worker())
