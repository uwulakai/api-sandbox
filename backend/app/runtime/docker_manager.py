import json
import time
from urllib.parse import urlparse

import docker
from docker.models.containers import Container

from app.config import settings
from app.entities.models import Mock, MockEndpoint


class DockerRuntimeManager:
    """Platform-owned Docker lifecycle adapter for Mock containers."""

    def __init__(self) -> None:
        self.client = docker.from_env()

    @staticmethod
    def container_name(mock: Mock) -> str:
        return f"api-sandbox-mock-{mock.id}"

    @staticmethod
    def labels(mock: Mock) -> dict[str, str]:
        mock_host = urlparse(settings.mock_public_base_url).hostname or "localhost"
        router_name = f"mock-{mock.id}"
        return {
            "com.api-sandbox.managed": "true",
            "com.api-sandbox.mock-id": mock.id,
            "com.api-sandbox.owner-id": str(mock.owner_id),
            "com.api-sandbox.config-version": str(mock.config_version),
            "traefik.enable": "true",
            f"traefik.http.routers.{router_name}.rule": (
                f"Host(`{mock_host}`) && PathPrefix(`/{mock.id}`)"
            ),
            f"traefik.http.routers.{router_name}.middlewares": f"{router_name}-strip",
            f"traefik.http.middlewares.{router_name}-strip.stripprefix.prefixes": f"/{mock.id}",
            f"traefik.http.services.{router_name}.loadbalancer.server.port": str(
                settings.mock_runtime_port
            ),
            "traefik.docker.network": settings.mock_network_name,
        }

    @staticmethod
    def config_payload(mock: Mock, endpoints: list[MockEndpoint]) -> str:
        return json.dumps(
            {
                "mock_id": mock.id,
                "config_version": mock.config_version,
                "endpoints": [
                    {
                        "method": endpoint.method,
                        "path": endpoint.path,
                        "status_code": endpoint.status_code,
                        "response_headers": endpoint.response_headers,
                        "response_body": endpoint.response_body,
                        "delay_ms": endpoint.delay_ms,
                        "enabled": endpoint.enabled,
                    }
                    for endpoint in endpoints
                ],
            },
            ensure_ascii=False,
        )

    def find(self, mock: Mock) -> Container | None:
        try:
            return self.client.containers.get(self.container_name(mock))
        except docker.errors.NotFound:
            return None

    def stop_and_remove(self, mock: Mock) -> None:
        container = self.find(mock)
        if container is None:
            return
        try:
            container.stop(timeout=10)
        except docker.errors.APIError:
            pass
        container.remove(force=True)

    def create(self, mock: Mock, endpoints: list[MockEndpoint]) -> Container:
        container = self.client.containers.run(
            settings.mock_runtime_image,
            detach=True,
            name=self.container_name(mock),
            network=settings.mock_network_name,
            environment={"MOCK_CONFIG_JSON": self.config_payload(mock, endpoints)},
            labels=self.labels(mock),
            read_only=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            mem_limit=settings.mock_runtime_memory_limit,
            cpu_period=settings.mock_runtime_cpu_period,
            cpu_quota=settings.mock_runtime_cpu_quota,
            restart_policy={"Name": "unless-stopped"},
        )
        deadline = time.monotonic() + settings.mock_runtime_healthcheck_timeout_seconds
        while time.monotonic() < deadline:
            container.reload()
            health = container.attrs.get("State", {}).get("Health", {})
            if health.get("Status") == "healthy":
                return container
            if container.status in {"exited", "dead"}:
                raise RuntimeError(f"Mock container exited during startup: {container.status}")
            time.sleep(1)
        raise TimeoutError("Mock container healthcheck timed out")

    def reconcile(
        self,
        mock: Mock,
        endpoints: list[MockEndpoint],
    ) -> str | None:
        self.stop_and_remove(mock)
        if mock.desired_status.value == "stopped":
            return None
        container = self.create(mock, endpoints)
        return container.id
