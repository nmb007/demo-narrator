"""Celery tasks for narration."""

from __future__ import annotations

import logging
from uuid import UUID

from celery import shared_task

from src.narration import service as narration_service
from src.narration.pipeline.ffmpeg_util import FFmpegError
from src.storage.exceptions import StorageIntegrityError

logger = logging.getLogger(__name__)


@shared_task(
    name="narration.run_narration",
    acks_late=True,
    max_retries=0,
)
def run_narration(run_id: str) -> None:
    try:
        narration_service.run_steps(UUID(run_id))
    except (
        OSError,
        FileNotFoundError,
        RuntimeError,
        FFmpegError,
        StorageIntegrityError,
        ValueError,
    ) as exc:
        logger.exception("Narration run %s failed: %s", run_id, exc)
        # run_steps already marks failed for any Exception
        raise
