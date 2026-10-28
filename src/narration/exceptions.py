"""Narration domain exceptions."""

from src.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError


class VideoNotFound(NotFoundError):
    """Video does not exist."""


class VideoNotOwned(ForbiddenError):
    """Caller does not own the video."""


class RunNotFound(NotFoundError):
    """Narration run does not exist."""


class RunInProgress(ConflictError):
    """A run for this video is already queued or running."""


class UnsupportedMediaType(AppError):
    """Uploaded file type is not supported."""


class InvalidDuration(AppError):
    """Video duration is outside allowed bounds."""


class OutputNotReady(NotFoundError):
    """No downloadable final video exists yet."""
