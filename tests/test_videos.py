"""API integration tests for GET /v1/videos."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from src.narration import service as narration_service
from src.narration.constants import NarrationStep, RunStatus
from src.narration.models import NarrationRun, Video
from tests.helpers import auth_headers, narrate_ok


def _set_run_status(run_id: UUID, status: RunStatus, *, created_offset_seconds: int = 0) -> None:
    with narration_service.get_sync_session() as session:
        run = session.get(NarrationRun, run_id)
        assert run is not None
        run.status = status
        run.created_at = datetime.now(UTC) - timedelta(seconds=created_offset_seconds)
        if status in (RunStatus.SUCCEEDED, RunStatus.FAILED):
            run.finished_at = datetime.now(UTC)
        session.add(run)
        session.commit()


def _add_run(
    *,
    video_id: UUID,
    status: RunStatus,
    created_offset_seconds: int = 0,
) -> NarrationRun:
    created = datetime.now(UTC) - timedelta(seconds=created_offset_seconds)
    with narration_service.get_sync_session() as session:
        run = NarrationRun(
            id=uuid4(),
            video_id=video_id,
            steps=[step.value for step in NarrationStep],
            options={},
            status=status,
            created_at=created,
            finished_at=created if status in (RunStatus.SUCCEEDED, RunStatus.FAILED) else None,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        session.expunge(run)
        return run


def _set_video_created_at(video_id: UUID, *, created_offset_seconds: int) -> None:
    with narration_service.get_sync_session() as session:
        video = session.get(Video, video_id)
        assert video is not None
        video.created_at = datetime.now(UTC) - timedelta(seconds=created_offset_seconds)
        session.add(video)
        session.commit()


@pytest.mark.asyncio
async def test_list_videos_200_empty(client: AsyncClient) -> None:
    headers = await auth_headers(client, email="videos-empty@example.com")
    response = await client.get("/v1/videos", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1
    assert body["size"] == 20
    assert body["pages"] == 0


@pytest.mark.asyncio
async def test_list_videos_200_own_newest_first(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = await auth_headers(client, email="videos-own@example.com")
    older = await narrate_ok(client, headers, monkeypatch, filename="older.mov")
    newer = await narrate_ok(client, headers, monkeypatch, filename="newer.mov")
    _set_video_created_at(UUID(older["video_id"]), created_offset_seconds=60)
    _set_video_created_at(UUID(newer["video_id"]), created_offset_seconds=10)
    _set_run_status(UUID(older["run_id"]), RunStatus.SUCCEEDED)
    _set_run_status(UUID(newer["run_id"]), RunStatus.SUCCEEDED)

    response = await client.get("/v1/videos", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [newer["video_id"], older["video_id"]]
    assert body["items"][0]["original_filename"] == "newer.mov"
    assert body["items"][0]["latest_run"]["run_id"] == newer["run_id"]
    assert body["items"][0]["latest_run"]["status"] == "succeeded"
    assert body["items"][1]["latest_run"]["run_id"] == older["run_id"]


@pytest.mark.asyncio
async def test_list_videos_latest_succeeded_run_only(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = await auth_headers(client, email="videos-latest@example.com")
    created = await narrate_ok(client, headers, monkeypatch)
    video_id = UUID(created["video_id"])
    _set_run_status(UUID(created["run_id"]), RunStatus.SUCCEEDED, created_offset_seconds=30)
    newer_success = _add_run(
        video_id=video_id,
        status=RunStatus.SUCCEEDED,
        created_offset_seconds=10,
    )
    _add_run(video_id=video_id, status=RunStatus.FAILED, created_offset_seconds=0)

    response = await client.get("/v1/videos", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["latest_run"]["run_id"] == str(newer_success.id)
    assert body["items"][0]["latest_run"]["status"] == "succeeded"


@pytest.mark.asyncio
async def test_list_videos_null_latest_run_when_none_succeeded(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = await auth_headers(client, email="videos-queued@example.com")
    created = await narrate_ok(client, headers, monkeypatch)

    response = await client.get("/v1/videos", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == created["video_id"]
    assert body["items"][0]["latest_run"] is None


@pytest.mark.asyncio
async def test_list_videos_hides_other_users(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await auth_headers(client, email="videos-owner@example.com")
    await narrate_ok(client, owner, monkeypatch)

    other = await auth_headers(client, email="videos-other@example.com")
    response = await client.get("/v1/videos", headers=other)
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_list_videos_pagination(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = await auth_headers(client, email="videos-page@example.com")
    created_ids: list[str] = []
    for index in range(3):
        created = await narrate_ok(
            client,
            headers,
            monkeypatch,
            filename=f"clip-{index}.mov",
        )
        created_ids.append(created["video_id"])
        _set_video_created_at(
            UUID(created["video_id"]),
            created_offset_seconds=30 - index,
        )
        _set_run_status(UUID(created["run_id"]), RunStatus.SUCCEEDED)

    page1 = await client.get("/v1/videos", headers=headers, params={"page": 1, "size": 2})
    assert page1.status_code == 200
    body1 = page1.json()
    assert body1["total"] == 3
    assert body1["page"] == 1
    assert body1["size"] == 2
    assert body1["pages"] == 2
    assert len(body1["items"]) == 2
    assert [item["id"] for item in body1["items"]] == [created_ids[2], created_ids[1]]

    page2 = await client.get("/v1/videos", headers=headers, params={"page": 2, "size": 2})
    assert page2.status_code == 200
    body2 = page2.json()
    assert body2["total"] == 3
    assert [item["id"] for item in body2["items"]] == [created_ids[0]]

    past_end = await client.get("/v1/videos", headers=headers, params={"page": 3, "size": 2})
    assert past_end.status_code == 200
    body3 = past_end.json()
    assert body3["items"] == []
    assert body3["total"] == 3


@pytest.mark.asyncio
async def test_list_videos_401_without_token(client: AsyncClient) -> None:
    response = await client.get("/v1/videos")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_videos_422_invalid_params(client: AsyncClient) -> None:
    headers = await auth_headers(client, email="videos-422@example.com")

    page_zero = await client.get("/v1/videos", headers=headers, params={"page": 0})
    assert page_zero.status_code == 422

    size_too_large = await client.get("/v1/videos", headers=headers, params={"size": 101})
    assert size_too_large.status_code == 422
