"""Narration FastAPI dependencies."""

from typing import Annotated
from uuid import UUID

from asyncer import asyncify
from fastapi import Depends, HTTPException, status

from src.auth.dependencies import CurrentUserDep
from src.narration import service as narration_service
from src.narration.exceptions import (
    OutputNotReady,
    RunInProgress,
    RunNotFound,
    VideoNotFound,
    VideoNotOwned,
)
from src.narration.models import NarrationRun, Video
from src.narration.schemas import RetryRequest


async def require_owned_video(video_id: UUID, user_id: UUID) -> Video:
    try:
        return await asyncify(narration_service.get_owned_video)(video_id, user_id)
    except VideoNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        ) from exc
    except VideoNotOwned as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        ) from exc


async def valid_owned_video(
    video_id: UUID,
    current_user: CurrentUserDep,
) -> Video:
    return await require_owned_video(video_id, current_user.id)


async def valid_owned_run(
    run_id: UUID,
    current_user: CurrentUserDep,
) -> NarrationRun:
    try:
        return await asyncify(narration_service.get_run)(run_id, current_user.id)
    except RunNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        ) from exc
    except VideoNotOwned as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        ) from exc


OwnedVideoDep = Annotated[Video, Depends(valid_owned_video)]
OwnedRunDep = Annotated[NarrationRun, Depends(valid_owned_run)]


async def valid_downloadable_run(video: OwnedVideoDep) -> NarrationRun:
    try:
        return await asyncify(narration_service.latest_downloadable_run)(video.id)
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


async def create_owned_retry_run(
    video: OwnedVideoDep,
    payload: RetryRequest,
) -> NarrationRun:
    try:
        return await asyncify(narration_service.create_retry_run)(
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


DownloadableRunDep = Annotated[NarrationRun, Depends(valid_downloadable_run)]
RetryRunDep = Annotated[NarrationRun, Depends(create_owned_retry_run)]
