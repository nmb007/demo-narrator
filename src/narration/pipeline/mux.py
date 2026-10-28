"""Mux aligned narration with source video."""

from __future__ import annotations

from src.narration.pipeline.ffmpeg_util import mux_video_audio
from src.narration.pipeline.paths import WorkPaths


def mux_video(
    paths: WorkPaths,
    *,
    force: bool = False,
) -> WorkPaths:
    if not paths.narration.is_file():
        raise FileNotFoundError(f"Missing narration.wav. Run voice first: {paths.narration}")

    if paths.final.exists() and not force:
        print(f"Skipping mux (final exists): {paths.final}")
        return paths

    print(f"Muxing {paths.source.name} + narration.wav -> {paths.final.name} ...")
    mux_video_audio(paths.source, paths.narration, paths.final)
    print(f"Wrote final video: {paths.final}")
    return paths
