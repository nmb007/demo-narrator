"""Edge TTS generation."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import edge_tts

from demo_mgr.align import align_narration
from demo_mgr.paths import DemoPaths, demo_paths, resolve_demo_dir


async def _synthesize_clip(text: str, voice: str, output_path: Path) -> None:
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))


def generate_voice(
    demo_dir_path: str | Path,
    *,
    voice: str | None = None,
    max_atempo: float = 1.20,
    force: bool = False,
) -> DemoPaths:
    demo_dir = resolve_demo_dir(demo_dir_path)
    paths = demo_paths(demo_dir)

    if not paths.script.exists():
        raise FileNotFoundError(f"Missing script.json. Run rewrite first: {paths.script}")

    selected_voice = voice or os.getenv("DEFAULT_VOICE", "en-US-AndrewNeural")

    if paths.narration.exists() and paths.sync_report.exists() and not force:
        print(f"Skipping voice (outputs exist). Use --force to rerun: {paths.demo_dir}")
        return paths

    script = json.loads(paths.script.read_text(encoding="utf-8"))
    chunks = script.get("chunks", [])
    if not chunks:
        raise ValueError(f"No chunks found in {paths.script}")

    missing = [chunk["id"] for chunk in chunks if not str(chunk.get("rewritten", "")).strip()]
    if missing:
        raise ValueError(
            f"Chunks missing rewritten text: {', '.join(missing)}. Run rewrite first or edit script.json."
        )

    paths.clips_dir.mkdir(parents=True, exist_ok=True)
    print(f"Generating TTS for {len(chunks)} chunks with voice '{selected_voice}'...")

    async def _run_all() -> None:
        tasks = []
        for chunk in chunks:
            clip_path = paths.clips_dir / f"{chunk['id']}.mp3"
            text = str(chunk["rewritten"]).strip()
            tasks.append(_synthesize_clip(text, selected_voice, clip_path))
        await asyncio.gather(*tasks)

    asyncio.run(_run_all())

    script["voice"] = selected_voice
    paths.script.write_text(json.dumps(script, indent=2), encoding="utf-8")

    report = align_narration(paths, max_atempo=max_atempo)
    paths.sync_report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _print_sync_table(report)
    print(f"Wrote narration: {paths.narration}")
    print(f"Wrote sync report: {paths.sync_report}")
    return paths


def _print_sync_table(report: dict) -> None:
    rows = report.get("chunks", [])
    if not rows:
        return
    print("")
    print(f"{'id':<12} {'orig':>6} {'tts':>6} {'window':>7} {'atempo':>7} status")
    print("-" * 50)
    for row in rows:
        print(
            f"{row['id']:<12} "
            f"{row['original_duration']:>6.2f} "
            f"{row['tts_duration']:>6.2f} "
            f"{row['window']:>7.2f} "
            f"{row['atempo']:>7.2f} "
            f"{row['status']}"
        )
