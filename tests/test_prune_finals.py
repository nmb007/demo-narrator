"""Unit tests for run-directory pruning."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlmodel import select

from src.auth import service as auth_service
from src.narration import service as narration_service
from src.narration import utils as key_utils
from src.narration.config import narration_settings
from src.narration.constants import NarrationStep, RunStatus
from src.narration.models import NarrationRun, Video
from src.storage import service as storage


@pytest.fixture
def user_id():
    user = auth_service.signup(f"prune-{uuid4().hex[:8]}@example.com", "password123")
    return user.id


def _create_video(user_id: UUID) -> UUID:
    video_id = uuid4()
    with narration_service.get_sync_session() as session:
        session.add(
            Video(
                id=video_id,
                user_id=user_id,
                original_filename="demo.mov",
                source_ext="mov",
            )
        )
        session.commit()
    return video_id


def _add_run(
    *,
    video_id: UUID,
    status: RunStatus,
    steps: list[str],
    finished_offset_seconds: int,
) -> NarrationRun:
    finished = datetime.now(UTC) - timedelta(seconds=finished_offset_seconds)
    with narration_service.get_sync_session() as session:
        run = NarrationRun(
            id=uuid4(),
            video_id=video_id,
            steps=steps,
            options={},
            status=status,
            finished_at=finished if status not in (RunStatus.QUEUED, RunStatus.RUNNING) else None,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        session.expunge(run)
        return run


def test_prune_keeps_newest_mux_successes_deletes_rest(
    user_id: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(narration_settings, "KEEP_FINALS", 2)
    deleted: list[str] = []
    monkeypatch.setattr(storage, "delete_prefix", lambda prefix: deleted.append(prefix))

    video_id = _create_video(user_id)
    all_steps = [s.value for s in NarrationStep]

    keep_newer = _add_run(
        video_id=video_id,
        status=RunStatus.SUCCEEDED,
        steps=all_steps,
        finished_offset_seconds=10,
    )
    keep_older = _add_run(
        video_id=video_id,
        status=RunStatus.SUCCEEDED,
        steps=all_steps,
        finished_offset_seconds=20,
    )
    old_mux = _add_run(
        video_id=video_id,
        status=RunStatus.SUCCEEDED,
        steps=all_steps,
        finished_offset_seconds=100,
    )
    failed = _add_run(
        video_id=video_id,
        status=RunStatus.FAILED,
        steps=["transcribe"],
        finished_offset_seconds=5,
    )
    non_mux = _add_run(
        video_id=video_id,
        status=RunStatus.SUCCEEDED,
        steps=["transcribe", "rewrite"],
        finished_offset_seconds=1,
    )
    active = _add_run(
        video_id=video_id,
        status=RunStatus.QUEUED,
        steps=all_steps,
        finished_offset_seconds=0,
    )

    narration_service.prune_finals(video_id)

    deleted_ids = {UUID(prefix.rsplit("/", 1)[-1]) for prefix in deleted}
    assert deleted_ids == {old_mux.id, failed.id, non_mux.id}
    assert key_utils.run_prefix(video_id, old_mux.id) in deleted
    assert keep_newer.id not in deleted_ids
    assert keep_older.id not in deleted_ids
    assert active.id not in deleted_ids

    # sanity: rows still in DB (prune is storage-only)
    with narration_service.get_sync_session() as session:
        assert len(session.exec(select(NarrationRun).where(NarrationRun.video_id == video_id)).all()) == 6
