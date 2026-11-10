import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.entities.models import Mock, MockEndpoint
from app.runtime.docker_manager import DockerRuntimeManager


@pytest.mark.parametrize(("defaults", "seconds"), [(True, 60), (False, 1)])
async def test_runtime_applies_mock_defaults(monkeypatch, defaults, seconds):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]))
    from mock_runtime.app import main

    mock = Mock(
        owner_id=1, name="Test", default_delay_ms=60_000,
        default_response_headers={"X-Shared": "mock", "X-Default": "inherited"},
    )
    endpoint = MockEndpoint(
        mock_id=mock.id, method="GET", path="/example", delay_ms=1000,
        response_body={"ok": True}, response_headers={"x-shared": "endpoint"},
    )
    config = json.loads(DockerRuntimeManager.config_payload(mock, [endpoint]))
    if not defaults:
        del config["default_delay_ms"]
        del config["default_response_headers"]
    sleep = AsyncMock()
    monkeypatch.setattr(main, "config", config)
    monkeypatch.setattr(main, "asyncio", SimpleNamespace(sleep=sleep))

    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://runtime") as client:
        unknown = await client.get("/unknown")
        assert unknown.status_code == 404 and "x-default" not in unknown.headers
        health = await client.get("/_internal/health")
        assert health.status_code == 200 and "x-default" not in health.headers
        sleep.assert_not_awaited()

        response = await client.get("/example")
    assert response.json() == {"ok": True}
    assert response.headers.get_list("x-shared") == ["endpoint"]
    assert response.headers.get("x-default") == ("inherited" if defaults else None)
    sleep.assert_awaited_once_with(seconds)
