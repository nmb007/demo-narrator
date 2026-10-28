"""Narration API routes."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from asyncer import asyncify
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from src.auth.dependencies import CurrentUserDep
from src.narration import service as narration_service
from src.narration import utils as key_utils
from src.narration.config import narration_settings
from src.narration.constants import NarrationStep, RunStatus
from src.narration.dependencies import OwnedRunDep, OwnedVideoDep, RetryOwnedVideoDep
from src.narration.exceptions import (
    OutputNotReady,
    RunInProgress,
    UnsupportedMediaType,
    VideoNotFound,
)
from src.narration.pipeline.ffmpeg_util import FFmpegError, probe_duration
from src.narration.schemas import RetryRequest, RunResponse, RunStatusResponse
from src.schemas import NOT_AUTHENTICATED_RESPONSE, error_response, success_response
from src.storage import service as storage
from src.storage.exceptions import UploadTooLarge

router = APIRouter(tags=["narration"])

ALLOWED_EXTS = {"mov", "mp4"}

_RUN_EXAMPLE = {
    "run_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "video_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    "status": "queued",
    "steps": ["transcribe", "rewrite", "voice", "mux"],
}
_RUN_STATUS_EXAMPLE = {
    **_RUN_EXAMPLE,
    "status": "running",
    "current_step": "rewrite",
    "error": None,
    "created_at": "2026-01-15T12:00:00Z",
    "started_at": "2026-01-15T12:00:05Z",
    "finished_at": None,
}


def _extension(filename: str | None) -> str:
    if not filename or "." not in filename:
        raise UnsupportedMediaType("Filename must end with .mov or .mp4")
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTS:
        raise UnsupportedMediaType("Only .mov and .mp4 uploads are supported")
    return ext


async def _probe_uploaded_duration(video_id: UUID, source_ext: str) -> float:
    key = key_utils.source_key(video_id, source_ext)
    if storage.is_local():
        return await asyncify(probe_duration)(storage.local_path(key))

    with tempfile.TemporaryDirectory(prefix="narration-probe-") as tmp:
        dest = Path(tmp) / f"source.{source_ext}"
        await asyncify(storage.download)(key, dest)
        return await asyncify(probe_duration)(dest)


@router.post(
    "/narrate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Narrate a video",
    description="Upload a video and queue the full narration pipeline.",
    responses={
        status.HTTP_202_ACCEPTED: success_response(
            model=RunResponse,
            description="Narration run queued",
            example=_RUN_EXAMPLE,
        ),
        **NOT_AUTHENTICATED_RESPONSE,
        status.HTTP_413_CONTENT_TOO_LARGE: error_response(
            description="Upload too large",
            detail="Upload exceeds maximum size",
        ),
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: error_response(
            description="Unsupported file type",
            detail="Only .mov and .mp4 uploads are supported",
        ),
        status.HTTP_422_UNPROCESSABLE_CONTENT: error_response(
            description="Invalid or unreadable video duration",
            examples={
                "duration": {
                    "summary": "Duration out of range",
                    "value": {
                        "detail": "Video duration must be between 2 and 600 seconds",
                    },
                },
                "unreadable": {
                    "summary": "Could not probe duration",
                    "value": {
                        "detail": "Could not read video duration: ffprobe failed",
                    },
                },
            },
        ),
    },
)
async def narrate(
    current_user: CurrentUserDep,
    video: Annotated[UploadFile, File()],
    model: Annotated[str | None, Form()] = None,
    voice: Annotated[str | None, Form()] = None,
    max_atempo: Annotated[float | None, Form()] = None,
) -> RunResponse:
    try:
        source_ext = _extension(video.filename)
    except UnsupportedMediaType as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc

    video_id = uuid4()
    key = key_utils.source_key(video_id, source_ext)

    async def chunks():
        while True:
            chunk = await video.read(1024 * 1024)
            if not chunk:
                break
            yield chunk

    try:
        await storage.put_stream(
            key,
            chunks(),
            max_bytes=narration_settings.MAX_UPLOAD_BYTES,
        )
    except UploadTooLarge as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(exc),
        ) from exc

    try:
        duration = await _probe_uploaded_duration(video_id, source_ext)
    except FFmpegError as exc:
        await storage.delete_async(key)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Could not read video duration: {exc}",
        ) from exc

    if (
        duration < narration_settings.MIN_DURATION_SECONDS
        or duration > narration_settings.MAX_DURATION_SECONDS
    ):
        await storage.delete_async(key)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Video duration must be between "
                f"{narration_settings.MIN_DURATION_SECONDS} and "
                f"{narration_settings.MAX_DURATION_SECONDS} seconds"
            ),
        )

    run = await asyncify(narration_service.create_video_and_run)(
        user_id=current_user.id,
        video_id=video_id,
        original_filename=video.filename or f"upload.{source_ext}",
        source_ext=source_ext,
        model=model,
        voice=voice,
        max_atempo=max_atempo,
    )
    await asyncify(narration_service.enqueue_run)(run.id)
    return RunResponse(
        run_id=run.id,
        video_id=run.video_id,
        status=RunStatus(run.status),
        steps=[NarrationStep(s) for s in run.steps],
    )


@router.post(
    "/retry",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry narration steps",
    description="Re-run one or more pipeline steps for an existing video.",
    responses={
        status.HTTP_202_ACCEPTED: success_response(
            model=RunResponse,
            description="Retry run queued",
            example=_RUN_EXAMPLE,
        ),
        **NOT_AUTHENTICATED_RESPONSE,
        status.HTTP_403_FORBIDDEN: error_response(
            description="Not the video owner",
            detail="Forbidden",
        ),
        status.HTTP_404_NOT_FOUND: error_response(
            description="Video not found",
            detail="Video not found",
        ),
        status.HTTP_409_CONFLICT: error_response(
            description="A run is already in progress",
            detail="A run is already queued or running for this video",
        ),
    },
)
async def retry(payload: RetryRequest, video: RetryOwnedVideoDep) -> RunResponse:
    try:
        run = await asyncify(narration_service.create_retry_run)(
            video_id=video.id,
            steps=payload.steps,
            model=payload.model,
            voice=payload.voice,
            max_atempo=payload.max_atempo,
        )
    except VideoNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        ) from exc
    except RunInProgress as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A run is already queued or running for this video",
        ) from exc

    await asyncify(narration_service.enqueue_run)(run.id)
    return RunResponse(
        run_id=run.id,
        video_id=run.video_id,
        status=RunStatus(run.status),
        steps=[NarrationStep(s) for s in run.steps],
    )


@router.get(
    "/runs/{run_id}",
    summary="Get run status",
    responses={
        status.HTTP_200_OK: success_response(
            model=RunStatusResponse,
            description="Run status",
            example=_RUN_STATUS_EXAMPLE,
        ),
        **NOT_AUTHENTICATED_RESPONSE,
        status.HTTP_403_FORBIDDEN: error_response(
            description="Forbidden",
            detail="Forbidden",
        ),
        status.HTTP_404_NOT_FOUND: error_response(
            description="Run not found",
            detail="Run not found",
        ),
    },
)
async def get_run_status(run: OwnedRunDep) -> RunStatusResponse:
    return RunStatusResponse(
        run_id=run.id,
        video_id=run.video_id,
        status=RunStatus(run.status),
        steps=[NarrationStep(s) for s in run.steps],
        current_step=NarrationStep(run.current_step) if run.current_step else None,
        error=run.error,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


@router.get(
    "/videos/{video_id}/download",
    summary="Download latest narrated video",
    response_class=StreamingResponse,
    responses={
        status.HTTP_200_OK: {
            "description": "Narrated MP4 video",
            "content": {
                "video/mp4": {
                    "schema": {"type": "string", "format": "binary"},
                }
            },
        },
        **NOT_AUTHENTICATED_RESPONSE,
        status.HTTP_403_FORBIDDEN: error_response(
            description="Forbidden",
            detail="Forbidden",
        ),
        status.HTTP_404_NOT_FOUND: error_response(
            description="Video or output not found",
            examples={
                "missing_video": {
                    "summary": "Video not found",
                    "value": {"detail": "Video not found"},
                },
                "not_ready": {
                    "summary": "Output not ready",
                    "value": {"detail": "No narrated output is ready yet"},
                },
            },
        ),
    },
)
async def download_video(video: OwnedVideoDep):
    try:
        run = await asyncify(narration_service.latest_downloadable_run)(video.id)
    except VideoNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        ) from exc
    except OutputNotReady as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No narrated output is ready yet",
        ) from exc

    key = key_utils.final_key(video.id, run.id)
    filename = f"{Path(video.original_filename).stem}-narrated.mp4"

    async def body():
        async for chunk in storage.open_stream(key):
            yield chunk

    return StreamingResponse(
        body(),
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
