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
    monkeypatch.setenv("E2E_OWNER_EMAIL", "owner@example.com")
    monkeypatch.setenv("E2E_OWNER_PASSWORD", "private-owner-password")
    monkeypatch.setenv("E2E_OTHER_EMAIL", "other@example.com")
    monkeypatch.setenv("E2E_OTHER_PASSWORD", "private-other-password")
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
        lambda request: httpx.Response(200, json={"token": "private-token"})
    ))
    account = client.account("owner")
    raw = Path(client.report_dir, "resources.json").read_text(encoding="utf-8")
    assert account["email"] in raw
    assert account["password"] not in raw and "private-token" not in raw
    assert json.loads(raw)["accounts"][0]["login"] == "succeeded"


def test_unknown_login_is_recorded(client):
    def handler(request):
        raise httpx.ReadTimeout("timeout", request=request)

    client.client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(pytest.fail.Exception):
        client.account("owner")
    manifest = json.loads(Path(client.report_dir, "resources.json").read_text(encoding="utf-8"))
    assert manifest["accounts"][0]["login"] == "unknown"


def test_full_requires_two_distinct_accounts(client, monkeypatch):
    monkeypatch.delenv("E2E_OTHER_PASSWORD")
    with pytest.raises(pytest.fail.Exception, match="E2E_OTHER_PASSWORD"):
        client.account("owner")
    monkeypatch.setenv("E2E_OTHER_PASSWORD", "private-other-password")
    monkeypatch.setenv("E2E_OTHER_EMAIL", "OWNER@example.com")
    with pytest.raises(pytest.fail.Exception, match="two different"):
        client.account("owner")
    assert client.accounts == []


def test_readiness_waits_for_new_response(client, monkeypatch):
    replies = iter([httpx.Response(404), httpx.Response(200, json={"v": 1}),
                    httpx.Response(200, json={"v": 2})])

    def handler(request):
        response = next(replies)
        response.headers["X-Request-ID"] = request.headers["X-Request-ID"]
        return response

    client.client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(support.time, "sleep", lambda seconds: None)
    mock = {"id": "test", "public_url": "https://mocks.example.test/test"}
    assert client.wait_public(mock, body={"v": 2}).json() == {"v": 2}


@pytest.mark.parametrize("expected", [200, 404])
def test_public_route_rejects_unrelated_proxy_404(client, expected):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(404, text="404 page not found\n")

    client.client = httpx.Client(transport=httpx.MockTransport(handler))
    mock = {"id": "test", "public_url": "https://wrong-domain.example.test/test"}
    with pytest.raises(pytest.fail.Exception, match="MOCK_PUBLIC_BASE_URL"):
        client.wait_public(mock, status=expected)
    assert len(calls) == 1


def test_public_route_rejects_stale_request_id(client):
    client.client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(404, headers={"X-Request-ID": "stale-request"})
    ))
    mock = {"id": "test", "public_url": "https://mocks.example.test/test"}
    with pytest.raises(pytest.fail.Exception, match="matching X-Request-ID"):
        client.wait_public(mock, status=404)


def test_public_route_accepts_gateway_404(client):
    client.client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(
            404,
            json={"detail": "Mock server not found or not running"},
            headers={"X-Request-ID": request.headers["X-Request-ID"]},
        )
    ))
    mock = {"id": "test", "public_url": "https://mocks.example.test/test"}
    assert client.wait_public(mock, path="/_internal/health", status=404).status_code == 404


@pytest.mark.parametrize("gateway_available", [True, False])
def test_cleanup_recovers_timed_out_creation_without_touching_other_mocks(client, gateway_available):
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
        headers = {"X-Request-ID": request.headers["X-Request-ID"]} if gateway_available else {}
        return httpx.Response(404, headers=headers)

    client.client = httpx.Client(transport=httpx.MockTransport(handler))
    fixture = support.mocks.__wrapped__(client, {"email": "test@example.com", "token": "private-token"})
    create = next(fixture)
    with pytest.raises(pytest.fail.Exception, match="ReadTimeout"):
        create()
    if gateway_available:
        with pytest.raises(StopIteration):
            next(fixture)
        assert client.resources[0]["cleanup"] == "api_deleted_and_runtime_unreachable"
    else:
        with pytest.raises(pytest.fail.Exception, match="Mock cleanup failed.*MOCK_PUBLIC_BASE_URL"):
            next(fixture)
        assert client.resources[0]["cleanup"] == "failed"
        assert client.resources[0]["api_deleted"] is True
    assert client.resources[0]["id"] == "owned"
    assert [call for call in calls if call[0] == "POST"] == [("POST", "/api/v1/mocks")]
