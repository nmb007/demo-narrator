"""API integration tests for GET /v1/videos/{video_id}/download."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from src.narration import service as narration_service
from src.narration import utils as key_utils
from src.storage import service as storage
from tests.helpers import auth_headers, narrate_ok


def _put_final(video_id: str, run_id: str, content: bytes = b"fake-mp4-bytes") -> None:
    key = key_utils.final_key(UUID(video_id), UUID(run_id))
    with NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        path = Path(tmp.name)
        path.write_bytes(content)
    try:
        storage.upload(path, key)
    finally:
        path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_download_200(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    headers = await auth_headers(client, email="dl-ok@example.com")
    created = await narrate_ok(client, headers, monkeypatch)
    narration_service.mark_run_succeeded(UUID(created["run_id"]))
    _put_final(created["video_id"], created["run_id"])

    response = await client.get(
        f"/v1/videos/{created['video_id']}/download",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("video/mp4")
    assert b"fake-mp4-bytes" in response.content


@pytest.mark.asyncio
async def test_download_401_without_token(client: AsyncClient) -> None:
    response = await client.get(f"/v1/videos/{uuid4()}/download")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_download_404_missing_video(client: AsyncClient) -> None:
    headers = await auth_headers(client, email="dl-404v@example.com")
    response = await client.get(f"/v1/videos/{uuid4()}/download", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found"


@pytest.mark.asyncio
async def test_download_404_output_not_ready(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = await auth_headers(client, email="dl-404o@example.com")
    created = await narrate_ok(client, headers, monkeypatch)
    # Run is still queued — no succeeded mux output.
    response = await client.get(
        f"/v1/videos/{created['video_id']}/download",
        headers=headers,
    )
    assert response.status_code == 404
    assert "ready" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_download_403_not_owner(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await auth_headers(client, email="dl-owner@example.com")
    created = await narrate_ok(client, owner, monkeypatch)
    narration_service.mark_run_succeeded(UUID(created["run_id"]))
    _put_final(created["video_id"], created["run_id"])

    other = await auth_headers(client, email="dl-other@example.com")
    response = await client.get(
        f"/v1/videos/{created['video_id']}/download",
        headers=other,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_download_422_invalid_uuid(client: AsyncClient) -> None:
    headers = await auth_headers(client, email="dl-422@example.com")
    response = await client.get("/v1/videos/not-a-uuid/download", headers=headers)
    assert response.status_code == 422
