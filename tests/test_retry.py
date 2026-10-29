"""API integration tests for POST /v1/videos/{video_id}/retry."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from src.narration import service as narration_service
from src.narration.constants import NarrationStep, RunStatus
from tests.helpers import auth_headers, enqueued_runs, narrate_ok


@pytest.mark.asyncio
async def test_retry_202(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    headers = await auth_headers(client, email="retry-ok@example.com")
    created = await narrate_ok(client, headers, monkeypatch)
    # Clear queued status so a retry is allowed.
    narration_service.mark_run_succeeded(UUID(created["run_id"]))

    response = await client.post(
        f"/v1/videos/{created['video_id']}/retry",
        headers=headers,
        json={
            "steps": ["voice", "mux"],
            "voice": "en-US-JennyNeural",
        },
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["video_id"] == created["video_id"]
    assert body["status"] == RunStatus.QUEUED
    assert body["steps"] == [NarrationStep.VOICE.value, NarrationStep.MUX.value]
    assert str(body["run_id"]) in enqueued_runs()


@pytest.mark.asyncio
async def test_retry_202_defaults_to_all_steps(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = await auth_headers(client, email="retry-all@example.com")
    created = await narrate_ok(client, headers, monkeypatch)
    narration_service.mark_run_succeeded(UUID(created["run_id"]))

    response = await client.post(
        f"/v1/videos/{created['video_id']}/retry",
        headers=headers,
        json={},
    )
    assert response.status_code == 202
    assert response.json()["steps"] == [s.value for s in NarrationStep]


@pytest.mark.asyncio
async def test_retry_401_without_token(client: AsyncClient) -> None:
    response = await client.post(f"/v1/videos/{uuid4()}/retry", json={})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_retry_404_missing_video(client: AsyncClient) -> None:
    headers = await auth_headers(client, email="retry-404@example.com")
    response = await client.post(
        f"/v1/videos/{uuid4()}/retry",
        headers=headers,
        json={"steps": ["mux"]},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_retry_403_not_owner(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await auth_headers(client, email="retry-owner@example.com")
    created = await narrate_ok(client, owner, monkeypatch)
    narration_service.mark_run_succeeded(UUID(created["run_id"]))

    other = await auth_headers(client, email="retry-other@example.com")
    response = await client.post(
        f"/v1/videos/{created['video_id']}/retry",
        headers=other,
        json={},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_retry_409_run_in_progress(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = await auth_headers(client, email="retry-409@example.com")
    created = await narrate_ok(client, headers, monkeypatch)
    # Original narrate left a queued run; retry must conflict.
    response = await client.post(
        f"/v1/videos/{created['video_id']}/retry",
        headers=headers,
        json={},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_retry_422_invalid_body(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = await auth_headers(client, email="retry-422@example.com")
    created = await narrate_ok(client, headers, monkeypatch)
    narration_service.mark_run_succeeded(UUID(created["run_id"]))
    response = await client.post(
        f"/v1/videos/{created['video_id']}/retry",
        headers=headers,
        json={"max_atempo": -1},
    )
    assert response.status_code == 422
