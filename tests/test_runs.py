"""API integration tests for GET /v1/runs/{run_id}."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from tests.helpers import auth_headers, narrate_ok


@pytest.mark.asyncio
async def test_get_run_200(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    headers = await auth_headers(client, email="runs-ok@example.com")
    created = await narrate_ok(client, headers, monkeypatch)

    response = await client.get(f"/v1/runs/{created['run_id']}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == created["run_id"]
    assert body["video_id"] == created["video_id"]
    assert body["status"] == "queued"
    assert body["steps"] == created["steps"]
    assert "created_at" in body


@pytest.mark.asyncio
async def test_get_run_401_without_token(client: AsyncClient) -> None:
    response = await client.get(f"/v1/runs/{uuid4()}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_run_404_missing(client: AsyncClient) -> None:
    headers = await auth_headers(client, email="runs-404@example.com")
    response = await client.get(f"/v1/runs/{uuid4()}", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_run_403_not_owner(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await auth_headers(client, email="runs-owner@example.com")
    created = await narrate_ok(client, owner, monkeypatch)

    other = await auth_headers(client, email="runs-other@example.com")
    response = await client.get(f"/v1/runs/{created['run_id']}", headers=other)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_run_422_invalid_uuid(client: AsyncClient) -> None:
    headers = await auth_headers(client, email="runs-422@example.com")
    response = await client.get("/v1/runs/not-a-uuid", headers=headers)
    assert response.status_code == 422
