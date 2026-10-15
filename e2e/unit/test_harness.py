"""Offline safety checks for the live-test harness (no network or real accounts)."""

import importlib.util
import json
import logging
from pathlib import Path

import httpx
import pytest


spec = importlib.util.spec_from_file_location(
    "live_support", Path(__file__).resolve().parents[1] / "tests" / "conftest.py"
)
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("API_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("E2E_REPORT_DIR", str(tmp_path))
    monkeypatch.setenv("E2E_RUN_ID", "offline")
    monkeypatch.delenv("E2E_HTTP_TIMEOUT", raising=False)
    monkeypatch.delenv("E2E_WAIT_SECONDS", raising=False)
    api = support.LiveAPI()
    api.client.close()
    yield api
    api.client.close()


@pytest.mark.parametrize("value", ["nan", "inf", "0", "-1", "garbage"])
def test_invalid_timeouts(monkeypatch, value):
    monkeypatch.setenv("E2E_WAIT_SECONDS", value)
    with pytest.raises(pytest.UsageError):
        support.positive_timeout("E2E_WAIT_SECONDS", "90")


@pytest.mark.parametrize("url", ["file:///tmp/api", "https://user:secret@example.test", "https://api.test?key=secret"])
def test_unsafe_api_urls(monkeypatch, url):
    monkeypatch.setenv("API_BASE_URL", url)
    with pytest.raises(pytest.UsageError):
        support.LiveAPI()


def test_request_log_redacts_secrets(client, caplog):
    def handler(request):
        assert request.headers["authorization"] == "Bearer private-token"
        assert request.headers["x-request-id"].startswith("e2e-offline-")
        return httpx.Response(200, json={"token": "response-secret"})

    client.client = httpx.Client(transport=httpx.MockTransport(handler))
    with caplog.at_level(logging.INFO, logger="e2e"):
        client.request("POST", "/test?password=query-secret", token="private-token",
                       json={"password": "body-secret"}, expected=200)
    for secret in ("private-token", "query-secret", "body-secret", "response-secret"):
        assert secret not in caplog.text
    assert "https://api.example.test/test -> 200" in caplog.text


def test_timeouts_are_logged_without_retrying_writes(client, caplog):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("potentially-sensitive-exception-text", request=request)

    client.client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(pytest.fail.Exception, match="ReadTimeout"):
        client.request("POST", "/test")
    assert len(calls) == 1
    assert "ReadTimeout" in caplog.text
    assert "potentially-sensitive" not in caplog.text


def test_resource_manifest_never_contains_credentials(client):
    client.client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(201, json={"token": "private-token"})
    ))
    account = client.account()
    raw = Path(client.report_dir, "resources.json").read_text(encoding="utf-8")
    assert account["email"] in raw
    assert account["password"] not in raw and "private-token" not in raw
    assert json.loads(raw)["accounts"][0]["registration"] == "created"


def test_unknown_registration_is_recorded(client):
    def handler(request):
        raise httpx.ReadTimeout("timeout", request=request)

    client.client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(pytest.fail.Exception):
        client.account()
    manifest = json.loads(Path(client.report_dir, "resources.json").read_text(encoding="utf-8"))
    assert manifest["accounts"][0]["registration"] == "unknown"


def test_readiness_waits_for_new_response(client, monkeypatch):
    replies = iter([httpx.Response(404), httpx.Response(200, json={"v": 1}),
                    httpx.Response(200, json={"v": 2})])
    client.client = httpx.Client(transport=httpx.MockTransport(lambda request: next(replies)))
    monkeypatch.setattr(support.time, "sleep", lambda seconds: None)
    mock = {"id": "test", "public_url": "https://mocks.example.test/test"}
    assert client.wait_public(mock, body={"v": 2}).json() == {"v": 2}


def test_cleanup_recovers_timed_out_creation_without_touching_other_mocks(client):
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.method == "POST":
            raise httpx.ReadTimeout("response lost after commit", request=request)
        if request.url.path == "/api/v1/mocks":
            return httpx.Response(200, json=[
                {"id": "owned", "name": client.resources[0]["name"],
                 "public_url": "https://mocks.example.test/owned"},
                {"id": "unrelated", "name": "do-not-touch"},
            ])
        if request.method == "DELETE":
            assert request.url.path == "/api/v1/mocks/owned"
            return httpx.Response(204)
        return httpx.Response(404)

    client.client = httpx.Client(transport=httpx.MockTransport(handler))
    fixture = support.mocks.__wrapped__(client, {"email": "test@example.com", "token": "private-token"})
    create = next(fixture)
    with pytest.raises(pytest.fail.Exception, match="ReadTimeout"):
        create()
    with pytest.raises(StopIteration):
        next(fixture)
    assert client.resources[0]["cleanup"] == "api_deleted_and_runtime_unreachable"
    assert client.resources[0]["id"] == "owned"
    assert [call for call in calls if call[0] == "POST"] == [("POST", "/api/v1/mocks")]
