"""Narration persistence models."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Column
from sqlmodel import Field

from src.models import TimestampModel, UUIDModel
from src.narration.constants import RunStatus


class Video(UUIDModel, TimestampModel, table=True):
    __tablename__ = "video"

    user_id: UUID = Field(foreign_key="user.id", index=True)
    original_filename: str = Field(max_length=512)
    source_ext: str = Field(max_length=8)


class NarrationRun(UUIDModel, TimestampModel, table=True):
    __tablename__ = "narration_run"

    video_id: UUID = Field(foreign_key="video.id", index=True)
    steps: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    options: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    status: str = Field(default=RunStatus.QUEUED, max_length=32, index=True)
    current_step: str | None = Field(default=None, max_length=32)
    error: str | None = Field(default=None)
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)
