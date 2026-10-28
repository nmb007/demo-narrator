"""Narration FastAPI dependencies."""

from typing import Annotated
from uuid import UUID

from asyncer import asyncify
from fastapi import Depends

from src.auth.dependencies import CurrentUserDep
from src.narration import service as narration_service
from src.narration.models import Video


async def valid_owned_video(
    video_id: UUID,
    current_user: CurrentUserDep,
) -> Video:
    return await asyncify(narration_service.get_owned_video)(video_id, current_user.id)


OwnedVideoDep = Annotated[Video, Depends(valid_owned_video)]
