"""Storage key helpers for narration artifacts."""

from uuid import UUID

VIDEO_PREFIX = "videos"


def video_prefix(video_id: UUID) -> str:
    return f"{VIDEO_PREFIX}/{video_id}"


def source_key(video_id: UUID, source_ext: str) -> str:
    return f"{video_prefix(video_id)}/source.{source_ext}"


def work_key(video_id: UUID, name: str) -> str:
    base = f"{video_prefix(video_id)}/work"
    if not name:
        return base
    return f"{base}/{name}"


def final_key(video_id: UUID, run_id: UUID) -> str:
    return f"{video_prefix(video_id)}/runs/{run_id}/final.mp4"
