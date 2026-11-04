"""Narration request and response schemas."""

from datetime import datetime
from typing import TypeVar
from uuid import UUID

from fastapi import Query
from fastapi_pagination import Page
from fastapi_pagination.customization import CustomizedPage, UseParamsFields
from pydantic import BaseModel, ConfigDict, Field

from src.narration.constants import NarrationStep, RunStatus

_SAMPLE_RUN_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_SAMPLE_VIDEO_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
_SAMPLE_STEPS = ["transcribe", "rewrite", "voice", "mux"]

T = TypeVar("T")

VideoPage = CustomizedPage[
    Page[T],
    UseParamsFields(
        size=Query(20, ge=1, le=100),
    ),
]


class RetryRequest(BaseModel):
    steps: list[NarrationStep] | None = None
    model: str | None = None
    voice: str | None = None
    max_atempo: float | None = Field(default=None, gt=0)


class RunResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "run_id": _SAMPLE_RUN_ID,
                    "video_id": _SAMPLE_VIDEO_ID,
                    "status": "queued",
                    "steps": _SAMPLE_STEPS,
                }
            ]
        }
    )

    run_id: UUID
    video_id: UUID
    status: RunStatus
    steps: list[NarrationStep]


class RunStatusResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "run_id": _SAMPLE_RUN_ID,
                    "video_id": _SAMPLE_VIDEO_ID,
                    "status": "running",
                    "steps": _SAMPLE_STEPS,
                    "current_step": "rewrite",
                    "error": None,
                    "created_at": "2026-01-15T12:00:00Z",
                    "started_at": "2026-01-15T12:00:05Z",
                    "finished_at": None,
                }
            ]
        }
    )

    run_id: UUID
    video_id: UUID
    status: RunStatus
    steps: list[NarrationStep]
    current_step: NarrationStep | None = None
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class VideoRunSummary(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "run_id": _SAMPLE_RUN_ID,
                    "status": "succeeded",
                    "current_step": None,
                    "created_at": "2026-01-15T12:00:00Z",
                    "started_at": "2026-01-15T12:00:05Z",
                    "finished_at": "2026-01-15T12:01:00Z",
                }
            ]
        }
    )

    run_id: UUID
    status: RunStatus
    current_step: NarrationStep | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class VideoListItem(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": _SAMPLE_VIDEO_ID,
                    "original_filename": "demo.mov",
                    "source_ext": "mov",
                    "created_at": "2026-01-15T12:00:00Z",
                    "latest_run": {
                        "run_id": _SAMPLE_RUN_ID,
                        "status": "succeeded",
                        "current_step": None,
                        "created_at": "2026-01-15T12:00:00Z",
                        "started_at": "2026-01-15T12:00:05Z",
                        "finished_at": "2026-01-15T12:01:00Z",
                    },
                }
            ]
        }
    )

    id: UUID
    original_filename: str
    source_ext: str
    created_at: datetime
    latest_run: VideoRunSummary | None = None
