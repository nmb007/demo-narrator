"""Path helpers for pipeline working directories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkPaths:
    work_dir: Path
    source: Path
    audio: Path
    transcript: Path
    script: Path
    clips_dir: Path
    narration: Path
    sync_report: Path
    final: Path


def resolve_workdir(path: str | Path) -> Path:
    work_dir = Path(path).expanduser().resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir


def work_paths(
    work_dir: Path,
    *,
    source: Path,
    final: Path,
) -> WorkPaths:
    return WorkPaths(
        work_dir=work_dir,
        source=source,
        audio=work_dir / "audio.wav",
        transcript=work_dir / "transcript.json",
        script=work_dir / "script.json",
        clips_dir=work_dir / "clips",
        narration=work_dir / "narration.wav",
        sync_report=work_dir / "sync-report.json",
        final=final,
    )
