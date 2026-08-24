"""Path helpers for demo folders."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DemoPaths:
    demo_dir: Path
    source: Path
    audio: Path
    transcript: Path
    script: Path
    clips_dir: Path
    narration: Path
    sync_report: Path
    final: Path


def resolve_demo_dir(path: str | Path) -> Path:
    demo_dir = Path(path).expanduser().resolve()
    if not demo_dir.is_dir():
        raise FileNotFoundError(f"Demo directory not found: {demo_dir}")
    return demo_dir


def find_source_video(demo_dir: Path, explicit: str | Path | None = None) -> Path:
    if explicit is not None:
        source = Path(explicit).expanduser()
        if not source.is_absolute():
            source = demo_dir / source
        source = source.resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Input video not found: {source}")
        return source

    mov = demo_dir / "source.mov"
    mp4 = demo_dir / "source.mp4"
    if mov.is_file():
        return mov
    if mp4.is_file():
        return mp4
    raise FileNotFoundError(
        f"No source video found in {demo_dir}. Expected source.mov or source.mp4."
    )


def demo_paths(demo_dir: Path, source: Path | None = None) -> DemoPaths:
    resolved_source = source or find_source_video(demo_dir)
    return DemoPaths(
        demo_dir=demo_dir,
        source=resolved_source,
        audio=demo_dir / "audio.wav",
        transcript=demo_dir / "transcript.json",
        script=demo_dir / "script.json",
        clips_dir=demo_dir / "clips",
        narration=demo_dir / "narration.wav",
        sync_report=demo_dir / "sync-report.json",
        final=demo_dir / "final.mp4",
    )
