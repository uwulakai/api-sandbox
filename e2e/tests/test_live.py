import os
import time

import pytest


@pytest.mark.parametrize("path", ["/health", "/health/liveness"])
def test_health(api, path):
    assert api.request("GET", path, expected=200).json() == {"status": "ok"}


@pytest.mark.parametrize("token", [None, "invalid-autotest-token"], ids=["missing", "invalid"])
def test_authentication_required(api, token):
    api.request("GET", "/api/v1/mocks", token=token, expected=401)


def test_registration_login_logout(api, owner):
    credentials = {"email": owner["email"], "password": owner["password"]}
    api.request("POST", "/api/v1/auth/register", json=credentials, expected=409)
    api.request("POST", "/api/v1/auth/login", expected=401,
                json={**credentials, "password": "definitely-wrong-password"})
    login = api.request("POST", "/api/v1/auth/login", json=credentials, expected=200)
    token = login.json()["token"]
    owner["tokens"].append(token)
    me = api.request("GET", "/api/v1/auth/me", token=token, expected=200).json()
    assert me["email"] == owner["email"] and me["is_active"] is True
    api.request("POST", "/api/v1/auth/logout", token=token, expected=200)
    api.request("GET", "/api/v1/auth/me", token=token, expected=401)
    api.request("GET", "/api/v1/auth/me", token=owner["token"], expected=200)


def test_mock_crud_and_api_stays_responsive(api, owner, mocks):
    mock = mocks(default_status=True)
    path = f"/api/v1/mocks/{mock['id']}"
    listed = api.request("GET", "/api/v1/mocks", token=owner["token"], expected=200).json()
    assert mock["id"] in [item["id"] for item in listed]
    updated = api.request("PATCH", path, token=owner["token"], expected=200,
                          json={"name": "E2E renamed", "description": "Updated by autotest"}).json()
    assert updated["config_version"] > mock["config_version"]
    api.wait_state(mock, owner["token"])
    assert api.request("GET", path, token=owner["token"], expected=200).json()["name"] == "E2E renamed"
    for _ in range(3):
        api.request("GET", "/api/v1/mocks", token=owner["token"], expected=200)
        api.request("GET", "/docs", expected=200)
        api.request("GET", "/health", expected=200)
        time.sleep(1)


def test_endpoint_crud_routing_methods_and_conflicts(api, owner, mocks):
    mock = mocks()
    token = owner["token"]
    path = f"/api/v1/mocks/{mock['id']}/endpoints"
    body = {"items": [{"id": 1, "name": "Alice"}]}
    endpoint = api.endpoint(mock, token, method="get", path="users/", response_body=body,
                            response_headers={"X-Mock": "true"})
    assert endpoint["method"] == "GET" and endpoint["path"] == "/users"
    assert api.request("GET", path + "/" + endpoint["id"], token=token, expected=200).json() == endpoint
    assert endpoint["id"] in [e["id"] for e in api.request("GET", path, token=token, expected=200).json()]
    api.request("POST", path, token=token, expected=409,
                json={"method": "GET", "path": "/users", "response_body": {}})
    api.action(mock, token, "start")
    result = api.wait_public(mock, path="/users", body=body)
    assert result.headers["x-mock"] == "true"
    api.request("GET", mock["public_url"] + "/not-found", expected=404)
    api.request("POST", mock["public_url"] + "/users", expected=404)
    assert api.request("GET", mock["public_url"] + "/users?tag=a&tag=b", expected=200).json() == body
    api.endpoint(mock, token, method="POST", path="/users", status_code=201, response_body={"created": True})
    api.wait_state(mock, token)
    api.wait_public(mock, path="/users", method="POST", status=201, body={"created": True})
    api.wait_public(mock, path="/users", body=body)


def test_endpoint_update_delay_disable_and_delete(api, owner, mocks):
    mock = mocks()
    token = owner["token"]
    endpoint = api.endpoint(mock, token)
    path = f"/api/v1/mocks/{mock['id']}/endpoints/{endpoint['id']}"
    api.action(mock, token, "start")
    api.wait_public(mock, body={"run": api.run_id})
    api.request("PATCH", path, token=token, expected=200, json={
        "status_code": 201, "response_body": {"updated": True},
        "response_headers": {"X-Revision": "two"}, "delay_ms": 800,
    })
    api.wait_state(mock, token)
    response = api.wait_public(mock, status=201, body={"updated": True})
    assert response.headers["x-revision"] == "two"
    assert response.elapsed.total_seconds() >= 0.70, "Configured response delay was not applied"
    api.request("PATCH", path, token=token, json={"enabled": False}, expected=200)
    api.wait_state(mock, token)
    api.wait_public(mock, status=404)
    api.request("PATCH", path, token=token, json={"enabled": True, "delay_ms": 0}, expected=200)
    api.wait_state(mock, token)
    api.wait_public(mock, status=201, body={"updated": True})
    api.request("DELETE", path, token=token, expected=204)
    api.request("GET", path, token=token, expected=404)
    api.wait_state(mock, token)
    api.wait_public(mock, status=404)


def test_stop_start_restart(api, owner, mocks):
    mock = mocks()
    token = owner["token"]
    api.endpoint(mock, token)
    api.action(mock, token, "start")
    api.wait_public(mock, body={"run": api.run_id})
    api.action(mock, token, "stop")
    api.wait_public(mock, status=404)
    api.action(mock, token, "start")
    api.wait_public(mock, body={"run": api.run_id})
    api.action(mock, token, "restart")
    api.wait_public(mock, body={"run": api.run_id})


def test_ownership_and_independent_mock_responses(api, owner, other, mocks):
    first = mocks()
    second = mocks(account=other)
    token = owner["token"]
    other_token = other["token"]
    endpoint = api.endpoint(first, token, response_body={"owner": "first"})
    api.endpoint(second, other_token, response_body={"owner": "second"})
    path = f"/api/v1/mocks/{first['id']}"
    for method, suffix, payload in [
        ("GET", "", None), ("PATCH", "", {"name": "must not change"}),
        ("DELETE", "", None), ("GET", "/endpoints", None),
        ("POST", "/stop", None), ("POST", "/start", None), ("POST", "/restart", None),
        ("POST", "/endpoints", {"method": "GET", "path": "/intruder"}),
        ("GET", f"/endpoints/{endpoint['id']}", None),
        ("PATCH", f"/endpoints/{endpoint['id']}", {"enabled": False}),
        ("DELETE", f"/endpoints/{endpoint['id']}", None),
    ]:
        api.request(method, path + suffix, token=other_token, json=payload, expected=404)
    listed = api.request("GET", "/api/v1/mocks", token=other_token, expected=200).json()
    assert first["id"] not in [m["id"] for m in listed]
    api.request("GET", f"/api/v1/mocks/{second['id']}/endpoints/{endpoint['id']}",
                token=other_token, expected=404)
    api.action(first, token, "start")
    api.action(second, other_token, "start")
    api.wait_public(first, body={"owner": "first"})
    api.wait_public(second, body={"owner": "second"})
    api.request("PATCH", path + f"/endpoints/{endpoint['id']}", token=token,
                json={"response_body": {"owner": "first-updated"}}, expected=200)
    api.wait_state(first, token)
    api.wait_public(first, body={"owner": "first-updated"})
    api.wait_public(second, body={"owner": "second"})


def test_validation(api, owner, mocks):
    mock = mocks()
    for changes in [{"method": "TRACE"}, {"status_code": 600}, {"status_code": 99},
                    {"delay_ms": -1}, {"delay_ms": 60001}, {"path": ""}]:
        api.request("POST", f"/api/v1/mocks/{mock['id']}/endpoints", token=owner["token"],
                    json={"method": "GET", "path": "/invalid", **changes}, expected=422)


def test_delete_running_mock(api, owner, mocks):
    mock = mocks()
    token = owner["token"]
    api.endpoint(mock, token)
    api.action(mock, token, "start")
    api.wait_public(mock, body={"run": api.run_id})
    api.request("DELETE", f"/api/v1/mocks/{mock['id']}", token=token, expected=204)
    api.request("GET", f"/api/v1/mocks/{mock['id']}", token=token, expected=404)
    listed = api.request("GET", "/api/v1/mocks", token=token, expected=200).json()
    assert mock["id"] not in [m["id"] for m in listed]
    api.wait_public(mock, status=404)
    api.wait_public(mock, path="/_internal/health", status=404)


@pytest.mark.docker
@pytest.mark.skipif(os.environ.get("E2E_DOCKER_INSPECT") != "1",
                    reason="Docker daemon access not configured; HTTP independence is tested separately")
def test_two_distinct_docker_containers_and_physical_removal(api, owner, mocks):
    import docker
    with docker.from_env() as daemon:
        first, second = mocks(running=True), mocks(running=True)
        containers = [daemon.containers.get(f"api-sandbox-mock-{m['id']}") for m in (first, second)]
        assert containers[0].id != containers[1].id
        for container in containers:
            assert container.status == "running"
            assert container.attrs["State"]["Health"]["Status"] == "healthy"
            assert container.labels["com.api-sandbox.managed"] == "true"
            assert not any(key.startswith("traefik.") for key in container.labels)
        api.request("DELETE", f"/api/v1/mocks/{first['id']}", token=owner["token"], expected=204)
        deadline = time.monotonic() + api.wait_seconds
        while time.monotonic() < deadline:
            try:
                containers[0].reload()
            except docker.errors.NotFound:
                break
            time.sleep(2)
        else:
            pytest.fail("Deleted Mock still has a Docker container")
        containers[1].reload()
        assert containers[1].status == "running"
