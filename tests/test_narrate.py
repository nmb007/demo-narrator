"""API integration tests for POST /v1/narrate."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from src.narration import router as narration_router
from src.narration.config import narration_settings
from src.narration.constants import NarrationStep
from src.narration.pipeline.ffmpeg_util import FFmpegError
from src.storage.exceptions import UploadTooLarge
from tests.helpers import auth_headers, enqueued_runs, narrate_ok, patch_duration


@pytest.mark.asyncio
async def test_narrate_202(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    headers = await auth_headers(client, email="narrate-ok@example.com")
    body = await narrate_ok(client, headers, monkeypatch)
    assert body["status"] == "queued"
    assert body["steps"] == [s.value for s in NarrationStep]
    assert body["run_id"]
    assert body["video_id"]
    assert str(body["run_id"]) in enqueued_runs()


@pytest.mark.asyncio
async def test_narrate_401_without_token(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/narrate",
        files={"video": ("demo.mov", b"bytes", "video/quicktime")},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_narrate_415_bad_extension(client: AsyncClient) -> None:
    headers = await auth_headers(client, email="narrate-415@example.com")
    response = await client.post(
        "/v1/narrate",
        headers=headers,
        files={"video": ("clip.txt", b"not-a-video", "text/plain")},
    )
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_narrate_413_too_large(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = await auth_headers(client, email="narrate-413@example.com")

    async def boom(*_args, **_kwargs):
        raise UploadTooLarge("Upload exceeds maximum size")

    monkeypatch.setattr("src.narration.router.storage.put_stream", boom)
    response = await client.post(
        "/v1/narrate",
        headers=headers,
        files={"video": ("demo.mov", b"bytes", "video/quicktime")},
    )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_narrate_422_duration_out_of_range(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = await auth_headers(client, email="narrate-dur@example.com")

    patch_duration(monkeypatch, narration_settings.MIN_DURATION_SECONDS - 1)
    too_short = await client.post(
        "/v1/narrate",
        headers=headers,
        files={"video": ("demo.mov", b"bytes", "video/quicktime")},
    )
    assert too_short.status_code == 422

    patch_duration(monkeypatch, narration_settings.MAX_DURATION_SECONDS + 1)
    too_long = await client.post(
        "/v1/narrate",
        headers=headers,
        files={"video": ("demo.mp4", b"bytes", "video/mp4")},
    )
    assert too_long.status_code == 422


@pytest.mark.asyncio
async def test_narrate_422_unreadable_media(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = await auth_headers(client, email="narrate-ff@example.com")

    async def boom(_video_id, _source_ext) -> float:
        raise FFmpegError("probe failed")

    monkeypatch.setattr(narration_router, "_probe_uploaded_duration", boom)
    response = await client.post(
        "/v1/narrate",
        headers=headers,
        files={"video": ("demo.mov", b"bytes", "video/quicktime")},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_narrate_422_missing_file(client: AsyncClient) -> None:
    headers = await auth_headers(client, email="narrate-missing@example.com")
    response = await client.post("/v1/narrate", headers=headers, data={})
    assert response.status_code == 422
