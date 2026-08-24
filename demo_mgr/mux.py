"""Mux aligned narration with source video."""

from __future__ import annotations

from demo_mgr.ffmpeg_util import mux_video_audio
from demo_mgr.paths import DemoPaths, demo_paths, resolve_demo_dir


def mux_demo(
    demo_dir_path: str | Path,
    *,
    force: bool = False,
) -> DemoPaths:
    demo_dir = resolve_demo_dir(demo_dir_path)
    paths = demo_paths(demo_dir)

    if not paths.narration.is_file():
        raise FileNotFoundError(f"Missing narration.wav. Run voice first: {paths.narration}")

    if paths.final.exists() and not force:
        print(f"Skipping mux (final exists). Use --force to rerun: {paths.final}")
        return paths

    print(f"Muxing {paths.source.name} + narration.wav -> final.mp4 ...")
    mux_video_audio(paths.source, paths.narration, paths.final)
    print(f"Wrote final video: {paths.final}")
    return paths
