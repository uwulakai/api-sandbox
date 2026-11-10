import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_auth_and_mock_endpoint_crud(client: AsyncClient, register_verified) -> None:
    headers = await register_verified("user@example.com")

    mock_response = await client.post(
        "/api/v1/mocks",
        headers=headers,
        json={
            "name": "Payments API",
            "default_response_headers": {"X-Mock": "payments"},
            "default_delay_ms": 200,
        },
    )
    assert mock_response.status_code == 201
    mock_id = mock_response.json()["id"]
    assert mock_response.json()["runtime_status"] == "pending"
    assert mock_response.json()["default_response_headers"] == {"X-Mock": "payments"}
    assert mock_response.json()["default_delay_ms"] == 200

    endpoint_response = await client.post(
        f"/api/v1/mocks/{mock_id}/endpoints",
        headers=headers,
        json={
            "method": "get",
            "path": "payments",
            "name": "List payments",
            "description": "Returns an empty collection",
            "status_code": 200,
            "response_body": {"items": []},
        },
    )
    assert endpoint_response.status_code == 201
    assert endpoint_response.json()["method"] == "GET"
    assert endpoint_response.json()["path"] == "/payments"
    assert endpoint_response.json()["name"] == "List payments"

    duplicate = await client.post(
        f"/api/v1/mocks/{mock_id}/endpoints",
        headers=headers,
        json={"method": "GET", "path": "/payments", "response_body": {}},
    )
    assert duplicate.status_code == 409

    listed = await client.get(f"/api/v1/mocks/{mock_id}/endpoints", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["description"] == "Returns an empty collection"

    endpoint = await client.patch(
        f"/api/v1/mocks/{mock_id}/endpoints/{endpoint_response.json()['id']}",
        headers=headers, json={"description": None},
    )
    assert endpoint.status_code == 200
    assert endpoint.json()["description"] is None
    assert endpoint.json()["name"] == "List payments"

    updated = await client.patch(f"/api/v1/mocks/{mock_id}", headers=headers, json={"default_delay_ms": 0})
    assert updated.status_code == 200
    assert updated.json()["default_delay_ms"] == 0
    assert updated.json()["default_response_headers"] == {"X-Mock": "payments"}
    assert updated.json()["config_version"] > mock_response.json()["config_version"]

    cleared = await client.patch(f"/api/v1/mocks/{mock_id}", headers=headers, json={"default_response_headers": {}})
    assert cleared.status_code == 200
    assert cleared.json()["default_response_headers"] == {}


@pytest.mark.parametrize("defaults", [
    {"default_response_headers": {"X-Foo": "a", "x-foo": "b"}},
    {"default_response_headers": {"Content-Length": "123"}},
    {"default_response_headers": {"X-Foo": "one\r\nX-Bar: two"}},
    {"default_response_headers": {"X-Foo": "кириллица"}},
    {"default_response_headers": None},
    {"default_delay_ms": 60_001},
])
def test_invalid_mock_defaults(defaults) -> None:
    from pydantic import ValidationError

    from app.entities.mocks.schemas import MockUpdate

    with pytest.raises(ValidationError):
        MockUpdate.model_validate(defaults)


@pytest.mark.asyncio
async def test_mock_resources_require_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/mocks")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unknown_mock_is_not_accessible(client: AsyncClient, register_verified) -> None:
    headers = await register_verified("owner@example.com")

    response = await client.get("/api/v1/mocks/not-owned", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_mock_isolation_between_users(client: AsyncClient, register_verified) -> None:
    owner_headers = await register_verified("owner@example.com")
    mock_response = await client.post(
        "/api/v1/mocks",
        headers=owner_headers,
        json={"name": "Private API"},
    )
    mock_id = mock_response.json()["id"]

    other_headers = await register_verified("other@example.com")

    response = await client.get(f"/api/v1/mocks/{mock_id}", headers=other_headers)
    assert response.status_code == 404
