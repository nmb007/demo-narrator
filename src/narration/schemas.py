"""Narration request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.narration.constants import NarrationStep, RunStatus

_SAMPLE_RUN_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_SAMPLE_VIDEO_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
_SAMPLE_STEPS = ["transcribe", "rewrite", "voice", "mux"]


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
