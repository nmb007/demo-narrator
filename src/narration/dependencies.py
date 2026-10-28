"""Narration FastAPI dependencies."""

from typing import Annotated
from uuid import UUID

from asyncer import asyncify
from fastapi import Depends, HTTPException, status

from src.auth.dependencies import CurrentUserDep
from src.narration import service as narration_service
from src.narration.exceptions import RunNotFound, VideoNotFound, VideoNotOwned
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


async def valid_owned_video_from_retry(
    payload: RetryRequest,
    current_user: CurrentUserDep,
) -> Video:
    return await require_owned_video(payload.video_id, current_user.id)


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
RetryOwnedVideoDep = Annotated[Video, Depends(valid_owned_video_from_retry)]
OwnedRunDep = Annotated[NarrationRun, Depends(valid_owned_run)]
