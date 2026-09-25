import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_auth_and_mock_endpoint_crud(client: AsyncClient) -> None:
    registration = await client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert registration.status_code == 201
    token = registration.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    mock_response = await client.post(
        "/api/v1/mocks",
        headers=headers,
        json={"name": "Payments API"},
    )
    assert mock_response.status_code == 201
    mock_id = mock_response.json()["id"]
    assert mock_response.json()["runtime_status"] == "pending"

    endpoint_response = await client.post(
        f"/api/v1/mocks/{mock_id}/endpoints",
        headers=headers,
        json={
            "method": "get",
            "path": "payments",
            "status_code": 200,
            "response_body": {"items": []},
        },
    )
    assert endpoint_response.status_code == 201
    assert endpoint_response.json()["method"] == "GET"
    assert endpoint_response.json()["path"] == "/payments"

    duplicate = await client.post(
        f"/api/v1/mocks/{mock_id}/endpoints",
        headers=headers,
        json={"method": "GET", "path": "/payments", "response_body": {}},
    )
    assert duplicate.status_code == 409

    listed = await client.get(f"/api/v1/mocks/{mock_id}/endpoints", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


@pytest.mark.asyncio
async def test_mock_resources_require_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/mocks")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unknown_mock_is_not_accessible(client: AsyncClient) -> None:
    registration = await client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {registration.json()['token']}"}

    response = await client.get("/api/v1/mocks/not-owned", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_mock_isolation_between_users(client: AsyncClient) -> None:
    owner_registration = await client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    owner_headers = {"Authorization": f"Bearer {owner_registration.json()['token']}"}
    mock_response = await client.post(
        "/api/v1/mocks",
        headers=owner_headers,
        json={"name": "Private API"},
    )
    mock_id = mock_response.json()["id"]

    other_registration = await client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "password123"},
    )
    other_headers = {"Authorization": f"Bearer {other_registration.json()['token']}"}

    response = await client.get(f"/api/v1/mocks/{mock_id}", headers=other_headers)
    assert response.status_code == 404
