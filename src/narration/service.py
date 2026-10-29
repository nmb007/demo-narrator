"""Narration sync domain services."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import desc
from sqlmodel import Session, col, select

from src.database import get_sync_session
from src.narration import utils as key_utils
from src.narration.config import narration_settings
from src.narration.constants import (
    ALL_STEPS,
    SOURCE,
    STEP_READS,
    STEP_WRITES,
    NarrationStep,
    RunStatus,
)
from src.narration.exceptions import (
    OutputNotReady,
    RunInProgress,
    RunNotFound,
    VideoNotFound,
    VideoNotOwned,
)
from src.narration.models import NarrationRun, Video
from src.storage import service as storage

logger = logging.getLogger(__name__)


def normalize_steps(steps: list[NarrationStep] | None) -> list[NarrationStep]:
    if not steps:
        return list(ALL_STEPS)
    wanted = set(steps)
    return [step for step in ALL_STEPS if step in wanted]


def required_inputs(steps: list[NarrationStep]) -> set[str]:
    produced: set[str] = set()
    needed: set[str] = set()
    for step in normalize_steps(steps):
        for artifact in STEP_READS[step]:
            if artifact not in produced:
                needed.add(artifact)
        produced |= STEP_WRITES[step]
    return needed


def get_video(session: Session, video_id: UUID) -> Video | None:
    return session.get(Video, video_id)


def get_owned_video(video_id: UUID, user_id: UUID) -> Video:
    with get_sync_session() as session:
        video = get_video(session, video_id)
        if video is None:
            raise VideoNotFound()
        if video.user_id != user_id:
            raise VideoNotOwned()
        session.expunge(video)
        return video


def get_run(run_id: UUID, user_id: UUID) -> NarrationRun:
    with get_sync_session() as session:
        run = session.get(NarrationRun, run_id)
        if run is None:
            raise RunNotFound()
        video = get_video(session, run.video_id)
        if video is None:
            raise RunNotFound()
        if video.user_id != user_id:
            raise VideoNotOwned()
        session.expunge(run)
        return run


def _assert_no_active_run(session: Session, video_id: UUID) -> None:
    active = session.exec(
        select(NarrationRun).where(
            NarrationRun.video_id == video_id,
            col(NarrationRun.status).in_([RunStatus.QUEUED, RunStatus.RUNNING]),
        )
    ).first()
    if active:
        raise RunInProgress()


def _merge_options(
    session: Session,
    video_id: UUID,
    *,
    model: str | None,
    voice: str | None,
    max_atempo: float | None,
) -> dict:
    previous = session.exec(
        select(NarrationRun)
        .where(NarrationRun.video_id == video_id)
        .order_by(desc(NarrationRun.created_at))
    ).first()
    prev_opts = previous.options if previous else {}
    return {
        "model": model or prev_opts.get("model") or narration_settings.WHISPER_MODEL,
        "voice": voice or prev_opts.get("voice") or narration_settings.DEFAULT_VOICE,
        "max_atempo": max_atempo
        if max_atempo is not None
        else float(prev_opts.get("max_atempo", 1.2)),
    }


def create_video_and_run(
    *,
    user_id: UUID,
    video_id: UUID,
    original_filename: str,
    source_ext: str,
    model: str | None = None,
    voice: str | None = None,
    max_atempo: float | None = None,
) -> NarrationRun:
    steps = list(ALL_STEPS)
    with get_sync_session() as session:
        video = Video(
            id=video_id,
            user_id=user_id,
            original_filename=original_filename,
            source_ext=source_ext,
        )
        options = {
            "model": model or narration_settings.WHISPER_MODEL,
            "voice": voice or narration_settings.DEFAULT_VOICE,
            "max_atempo": max_atempo if max_atempo is not None else 1.2,
        }
        run = NarrationRun(
            id=uuid4(),
            video_id=video_id,
            steps=[s.value for s in steps],
            options=options,
            status=RunStatus.QUEUED,
        )
        session.add(video)
        # Flush video first: without a Relationship(), the unit of work may
        # INSERT narration_run before video and trip the FK constraint.
        session.flush()
        session.add(run)
        session.commit()
        session.refresh(run)
        session.expunge(run)
        return run


def create_retry_run(
    *,
    video_id: UUID,
    steps: list[NarrationStep] | None,
    model: str | None = None,
    voice: str | None = None,
    max_atempo: float | None = None,
) -> NarrationRun:
    """Create a retry run. Caller must have already verified video ownership."""
    normalized = normalize_steps(steps)
    with get_sync_session() as session:
        video = get_video(session, video_id)
        if video is None:
            raise VideoNotFound()
        _assert_no_active_run(session, video_id)
        options = _merge_options(
            session,
            video_id,
            model=model,
            voice=voice,
            max_atempo=max_atempo,
        )
        run = NarrationRun(
            id=uuid4(),
            video_id=video_id,
            steps=[s.value for s in normalized],
            options=options,
            status=RunStatus.QUEUED,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        session.expunge(run)
        return run


def mark_run_running(run_id: UUID) -> NarrationRun:
    with get_sync_session() as session:
        run = session.get(NarrationRun, run_id)
        if run is None:
            raise RunNotFound()
        run.status = RunStatus.RUNNING
        run.started_at = datetime.now(UTC)
        run.error = None
        session.add(run)
        session.commit()
        session.refresh(run)
        session.expunge(run)
        return run


def mark_run_step(run_id: UUID, step: NarrationStep) -> None:
    with get_sync_session() as session:
        run = session.get(NarrationRun, run_id)
        if run is None:
            raise RunNotFound()
        run.current_step = step.value
        session.add(run)
        session.commit()


def mark_run_succeeded(run_id: UUID) -> NarrationRun:
    with get_sync_session() as session:
        run = session.get(NarrationRun, run_id)
        if run is None:
            raise RunNotFound()
        run.status = RunStatus.SUCCEEDED
        run.finished_at = datetime.now(UTC)
        session.add(run)
        session.commit()
        session.refresh(run)
        session.expunge(run)
        return run


def mark_run_failed(run_id: UUID, error: str) -> NarrationRun:
    with get_sync_session() as session:
        run = session.get(NarrationRun, run_id)
        if run is None:
            raise RunNotFound()
        run.status = RunStatus.FAILED
        run.error = error
        run.finished_at = datetime.now(UTC)
        session.add(run)
        session.commit()
        session.refresh(run)
        session.expunge(run)
        return run


def prune_finals(video_id: UUID) -> None:
    """Keep the newest KEEP_FINALS muxed success run dirs; delete all other run dirs.

    Removes older mux successes, failed runs, and succeeded non-mux runs under
    ``videos/{video_id}/runs/{run_id}/``. Active (queued/running) runs are left alone.
    """
    keep = narration_settings.KEEP_FINALS
    with get_sync_session() as session:
        runs = session.exec(
            select(NarrationRun)
            .where(NarrationRun.video_id == video_id)
            .order_by(desc(NarrationRun.finished_at), desc(NarrationRun.created_at))
        ).all()

        mux_succeeded = [
            run
            for run in runs
            if run.status == RunStatus.SUCCEEDED and NarrationStep.MUX.value in (run.steps or [])
        ]
        keep_ids = {run.id for run in mux_succeeded[:keep]}

        for run in runs:
            if run.id in keep_ids:
                continue
            if run.status in (RunStatus.QUEUED, RunStatus.RUNNING):
                continue
            try:
                storage.delete_prefix(key_utils.run_prefix(video_id, run.id))
            except Exception:  # noqa: BLE001
                logger.exception("Failed to prune run directory for %s", run.id)


def latest_downloadable_run(video_id: UUID) -> NarrationRun:
    """Return the latest muxed success run. Caller must have verified ownership."""
    with get_sync_session() as session:
        if get_video(session, video_id) is None:
            raise VideoNotFound()
        runs = session.exec(
            select(NarrationRun)
            .where(
                NarrationRun.video_id == video_id,
                NarrationRun.status == RunStatus.SUCCEEDED,
            )
            .order_by(desc(NarrationRun.finished_at))
        ).all()
        for run in runs:
            if NarrationStep.MUX.value in (run.steps or []):
                session.expunge(run)
                return run
        raise OutputNotReady()


def run_steps(run_id: UUID) -> None:
    # Import pipeline steps lazily so the API process does not load Whisper/pydub.
    from src.narration.pipeline.mux import mux_video
    from src.narration.pipeline.rewrite import rewrite_script
    from src.narration.pipeline.transcribe import transcribe_video
    from src.narration.pipeline.tts import generate_voice
    from src.narration.workspace import open_workspace

    with get_sync_session() as session:
        run = session.get(NarrationRun, run_id)
        if run is None:
            raise RunNotFound()
        video = get_video(session, run.video_id)
        if video is None:
            raise VideoNotFound()
        steps = [NarrationStep(s) for s in run.steps]
        options = dict(run.options or {})
        video_id = video.id
        source_ext = video.source_ext
        session.expunge(run)
        session.expunge(video)

    mark_run_running(run_id)
    workspace = open_workspace(
        video_id=video_id,
        run_id=run_id,
        source_ext=source_ext,
    )
    try:
        needed = required_inputs(steps)
        # Voice may need source if script lacks video_duration; after prepare of
        # script we can refine, so if voice is requested include source when
        # script is not produced earlier in this run.
        if NarrationStep.VOICE in steps and NarrationStep.TRANSCRIBE not in steps:
            needed.add(SOURCE)

        workspace.prepare(needed)
        if (
            NarrationStep.VOICE in steps
            and SOURCE not in needed
            and workspace.needs_source_for_voice()
        ):
            # download/check source if voice needs duration fallback
            extra = {SOURCE}
            workspace.prepare(extra)

        paths = workspace.paths
        model = options.get("model")
        voice = options.get("voice")
        max_atempo = float(options.get("max_atempo", 1.2))

        for step in steps:
            mark_run_step(run_id, step)
            if step == NarrationStep.TRANSCRIBE:
                transcribe_video(paths, model_name=model, force=True)
            elif step == NarrationStep.REWRITE:
                rewrite_script(paths, force=True)
            elif step == NarrationStep.VOICE:
                generate_voice(paths, voice=voice, max_atempo=max_atempo, force=True)
            elif step == NarrationStep.MUX:
                mux_video(paths, force=True)
            workspace.after_step(step)

        mark_run_succeeded(run_id)
    except Exception as exc:
        mark_run_failed(run_id, str(exc))
        raise
    finally:
        workspace.close()
        # Drop excess / failed / non-mux run dirs after every finished attempt.
        try:
            prune_finals(video_id)
        except Exception:  # noqa: BLE001
            logger.exception("prune_finals failed for video %s", video_id)


def enqueue_run(run_id: UUID) -> None:
    from src.narration.tasks import run_narration

    run_narration.delay(str(run_id))
