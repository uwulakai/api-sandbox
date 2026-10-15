import json
import logging
import math
import os
from pathlib import Path
import secrets
import time
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import pytest


log = logging.getLogger("e2e")


def positive_timeout(name, default):
    try:
        value = float(os.environ.get(name, default))
    except ValueError as exc:
        raise pytest.UsageError(f"{name} must be a positive finite number") from exc
    if not math.isfinite(value) or value <= 0:
        raise pytest.UsageError(f"{name} must be a positive finite number")
    return value


class LiveAPI:
    def __init__(self):
        base = os.environ.get("API_BASE_URL", "").rstrip("/")
        parsed = urlsplit(base)
        if (parsed.scheme not in {"https", "http"} or not parsed.netloc
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise pytest.UsageError("API_BASE_URL must be an HTTP(S) URL without credentials/query")
        self.base = base
        self.run_id = os.environ.get("E2E_RUN_ID", uuid4().hex)
        self.wait_seconds = positive_timeout("E2E_WAIT_SECONDS", "90")
        self.client = httpx.Client(timeout=positive_timeout("E2E_HTTP_TIMEOUT", "15"),
                                   follow_redirects=False, trust_env=False)
        self.accounts = []
        self.resources = []
        self.report_dir = os.environ.get("E2E_REPORT_DIR")
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

    def save_resources(self):
        if self.report_dir:
            Path(self.report_dir).mkdir(parents=True, exist_ok=True)
            Path(self.report_dir, "resources.json").write_text(json.dumps({
                "run_id": self.run_id, "api_url": self.base,
                "accounts": [{"email": a["email"], "registration": a["registration"],
                              "session_cleanup": a["session_cleanup"]} for a in self.accounts],
                "mocks": self.resources,
            }, indent=2), encoding="utf-8")

    def request(self, method, path, *, token=None, expected=None, **kwargs):
        headers = dict(kwargs.pop("headers", {}))
        request_id = f"e2e-{self.run_id}-{uuid4().hex[:8]}"
        headers["X-Request-ID"] = request_id
        if token:
            headers["Authorization"] = f"Bearer {token}"
        url = path if path.startswith(("http://", "https://")) else self.base + path
        # Log neither headers, query strings, request/response bodies nor auth tokens.
        safe_url = urlsplit(url)._replace(query="", fragment="").geturl()
        start = time.monotonic()
        try:
            response = self.client.request(method, url, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            message = (f"{method} {safe_url}: {type(exc).__name__}; "
                       f"elapsed_ms={(time.monotonic() - start) * 1000:.0f}; request_id={request_id}")
            log.error(message)
            pytest.fail(message, pytrace=False)
        log.info("%s %s -> %s %.0fms request_id=%s", method, safe_url,
                 response.status_code, (time.monotonic() - start) * 1000, request_id)
        if expected is not None:
            allowed = (expected,) if isinstance(expected, int) else expected
            assert response.status_code in allowed, (
                f"{method} {safe_url}: expected {allowed}, got {response.status_code}; "
                f"request_id={request_id}"
            )
        return response

    def account(self):
        email = f"e2e-{uuid4().hex}@example.com"
        password = secrets.token_urlsafe(24)
        account = {"email": email, "password": password, "tokens": [],
                   "registration": "unknown", "session_cleanup": "pending"}
        self.accounts.append(account)
        self.save_resources()
        response = self.request("POST", "/api/v1/auth/register", expected=201,
                                json={"email": email, "password": password})
        token = response.json()["token"]
        account.update(token=token, tokens=[token], registration="created")
        self.save_resources()
        return account

    def wait_state(self, mock, token, state="running"):
        deadline = time.monotonic() + self.wait_seconds
        previous = None
        while time.monotonic() < deadline:
            data = self.request("GET", f"/api/v1/mocks/{mock['id']}",
                                token=token, expected=200).json()
            actual = data["runtime_status"]
            if actual != previous:
                log.info("mock=%s runtime_status=%s desired_status=%s",
                         mock["id"], actual, data["desired_status"])
                previous = actual
            assert actual != "error", f"Mock {mock['id']} runtime error: {data.get('last_error')}"
            if actual == state:
                assert data["last_error"] is None
                return data
            time.sleep(2)
        pytest.fail(f"Mock {mock['id']} never reached {state}; last status={previous}")

    def wait_public(self, mock, *, path="/probe", status=200, body=None, method="GET"):
        deadline = time.monotonic() + self.wait_seconds
        last = None
        while time.monotonic() < deadline:
            response = self.request(method, mock["public_url"] + path)
            last = response.status_code
            if last == status:
                if body is None:
                    return response
                try:
                    if response.json() == body:
                        return response
                except ValueError:
                    pass
            time.sleep(2)
        pytest.fail(f"Public mock {mock['id']} never returned expected status/body: "
                    f"expected={status}, last_status={last}")

    def endpoint(self, mock, token, **changes):
        payload = {"method": "GET", "path": "/probe", "status_code": 200,
                   "response_body": {"run": self.run_id}, **changes}
        return self.request("POST", f"/api/v1/mocks/{mock['id']}/endpoints",
                            token=token, json=payload, expected=201).json()

    def action(self, mock, token, action):
        self.request("POST", f"/api/v1/mocks/{mock['id']}/{action}", token=token, expected=200)
        return self.wait_state(mock, token, "stopped" if action == "stop" else "running")


@pytest.fixture(scope="session")
def api():
    if not os.environ.get("API_BASE_URL"):
        pytest.skip("Set API_BASE_URL to opt in to testing a running deployment")
    service = LiveAPI()
    try:
        yield service
    finally:
        failures = []
        for account in service.accounts:
            account_failures = []
            for token in account["tokens"]:
                try:
                    service.request("POST", "/api/v1/auth/logout", token=token, expected=(200, 401))
                except (Exception, pytest.fail.Exception) as exc:
                    account_failures.append(str(exc))
            account["session_cleanup"] = ("unknown" if not account["tokens"] else
                                          "failed" if account_failures else "revoked")
            failures.extend(account_failures)
        service.save_resources()
        service.client.close()
        if failures:
            pytest.fail("Session cleanup failed: " + "; ".join(failures))


@pytest.fixture(scope="session")
def owner(api):
    return api.account()


@pytest.fixture(scope="session")
def other(api):
    return api.account()


@pytest.fixture
def mocks(api, owner):
    created = []

    def create(*, account=None, running=False, default_status=False):
        account = account or owner
        payload = {"name": f"e2e-{api.run_id}-{len(api.resources)}", "description": "Autotest"}
        if not default_status:
            payload["desired_status"] = "running" if running else "stopped"
        record = {"id": None, "name": payload["name"], "email": account["email"],
                  "cleanup": "creation_result_unknown"}
        api.resources.append(record)
        item = {"data": None, "token": account["token"], "record": record}
        created.append(item)
        api.save_resources()
        data = api.request("POST", "/api/v1/mocks", token=account["token"],
                           json=payload, expected=201).json()
        record.update(id=data["id"], cleanup="pending")
        item["data"] = data
        api.save_resources()
        api.wait_state(data, account["token"], "running" if running or default_status else "stopped")
        return data

    try:
        yield create
    finally:
        failures = []
        for item in reversed(created):
            data, token, record = item["data"], item["token"], item["record"]
            try:
                if data is None:
                    # A timed-out POST may have committed. Recover only this attempt,
                    # by its unique name and the same disposable account's token.
                    listed = api.request("GET", "/api/v1/mocks", token=token, expected=200).json()
                    matches = [mock for mock in listed if mock["name"] == record["name"]]
                    if len(matches) != 1:
                        raise RuntimeError("Creation result still unknown for " + record["name"])
                    data = matches[0]
                    record["id"] = data["id"]
                api.request("DELETE", f"/api/v1/mocks/{data['id']}", token=token, expected=(204, 404))
                api.request("GET", f"/api/v1/mocks/{data['id']}", token=token, expected=404)
                record["api_deleted"] = True
                api.save_resources()
                # /_internal/health distinguishes a removed runtime from a missing endpoint.
                api.wait_public(data, path="/_internal/health", status=404)
                record["cleanup"] = "api_deleted_and_runtime_unreachable"
            except (Exception, pytest.fail.Exception) as exc:
                record["cleanup"] = "failed"
                failures.append(str(exc))
            api.save_resources()
        if failures:
            pytest.fail("Mock cleanup failed: " + "; ".join(failures))
