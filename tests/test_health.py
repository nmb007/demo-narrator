"""API integration tests for health endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_200(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_cors_preflight_allows_local_frontend(client: AsyncClient) -> None:
    response = await client.options(
        "/v1/auth/signup",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers.get("access-control-allow-credentials") != "true"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"].lower()

    actual = await client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert actual.status_code == 200
    assert "content-disposition" in actual.headers["access-control-expose-headers"].lower()


@pytest.mark.asyncio
async def test_cors_preflight_rejects_other_origins(client: AsyncClient) -> None:
    response = await client.options(
        "/v1/auth/signup",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.headers.get("access-control-allow-origin") is None
