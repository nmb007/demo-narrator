"""Shared helpers for API integration tests."""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from src.main import app
from src.narration import router as narration_router


async def auth_headers(
    client: AsyncClient,
    *,
    email: str,
    password: str = "password123",
) -> dict[str, str]:
    await client.post(
        "/v1/auth/signup",
        json={"email": email, "password": password},
    )
    login = await client.post(
        "/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def patch_duration(monkeypatch: pytest.MonkeyPatch, seconds: float = 12.0) -> None:
    async def fake_probe(_video_id: UUID, _source_ext: str) -> float:
        return seconds

    monkeypatch.setattr(narration_router, "_probe_uploaded_duration", fake_probe)


async def narrate_ok(
    client: AsyncClient,
    headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    *,
    filename: str = "demo.mov",
    duration: float = 12.0,
) -> dict:
    patch_duration(monkeypatch, duration)
    response = await client.post(
        "/v1/narrate",
        headers=headers,
        files={"video": (filename, b"fake-video-bytes", "video/quicktime")},
    )
    assert response.status_code == 202, response.text
    return response.json()


def enqueued_runs() -> list[str]:
    return app.state.enqueued_runs  # type: ignore[attr-defined]
