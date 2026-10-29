"""Narration enums and step input/output maps."""

from enum import StrEnum


class NarrationStep(StrEnum):
    TRANSCRIBE = "transcribe"
    REWRITE = "rewrite"
    VOICE = "voice"
    MUX = "mux"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


ALL_STEPS: tuple[NarrationStep, ...] = (
    NarrationStep.TRANSCRIBE,
    NarrationStep.REWRITE,
    NarrationStep.VOICE,
    NarrationStep.MUX,
)

# Logical artifact names used by required_inputs / workspaces.
SOURCE = "source"
AUDIO = "audio.wav"
TRANSCRIPT = "transcript.json"
SCRIPT = "script.json"
CLIPS = "clips"
NARRATION = "narration.wav"
SYNC_REPORT = "sync-report.json"
FINAL = "final.mp4"

STEP_READS: dict[NarrationStep, frozenset[str]] = {
    NarrationStep.TRANSCRIBE: frozenset({SOURCE}),
    NarrationStep.REWRITE: frozenset({SCRIPT}),
    NarrationStep.VOICE: frozenset({SCRIPT}),
    NarrationStep.MUX: frozenset({SOURCE, NARRATION}),
}

STEP_WRITES: dict[NarrationStep, frozenset[str]] = {
    NarrationStep.TRANSCRIBE: frozenset({AUDIO, TRANSCRIPT, SCRIPT}),
    NarrationStep.REWRITE: frozenset({SCRIPT}),
    NarrationStep.VOICE: frozenset({CLIPS, NARRATION, SYNC_REPORT, SCRIPT}),
    NarrationStep.MUX: frozenset({FINAL}),
}
