"""Edge TTS generation."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import aiohttp
import edge_tts
from edge_tts.exceptions import NoAudioReceived, UnexpectedResponse, UnknownResponse, WebSocketError

from demo_mgr.align import align_narration
from demo_mgr.paths import DemoPaths, demo_paths, resolve_demo_dir

# Microsoft drops a burst of parallel TTS sockets and sometimes closes one
# socket without audio. Speak one chunk at a time and retry those drops.
_MAX_ATTEMPTS = 4
_RETRY_BASE_SECONDS = 1.5
_GAP_SECONDS = 0.5
_RETRYABLE = (
    NoAudioReceived,
    UnexpectedResponse,
    UnknownResponse,
    WebSocketError,
    aiohttp.ClientError,
    TimeoutError,
    ConnectionError,
    OSError,
)


def _remove_empty_clip(output_path: Path) -> None:
    if output_path.exists() and output_path.stat().st_size == 0:
        output_path.unlink()


async def _synthesize_clip(text: str, voice: str, output_path: Path) -> None:
    last_error: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(output_path))
            if output_path.stat().st_size > 0:
                return
            last_error = NoAudioReceived("No audio was received.")
        except _RETRYABLE as exc:
            last_error = exc
        _remove_empty_clip(output_path)
        if attempt == _MAX_ATTEMPTS:
            break
        delay = _RETRY_BASE_SECONDS * attempt
        print(
            f"  {output_path.name}: no audio (attempt {attempt}/{_MAX_ATTEMPTS}), "
            f"retrying in {delay:.1f}s"
        )
        await asyncio.sleep(delay)
    raise NoAudioReceived(
        f"No audio was received for {output_path.name} after {_MAX_ATTEMPTS} attempts."
    ) from last_error


async def _synthesize_all(chunks: list[dict], voice: str, clips_dir: Path) -> None:
    total = len(chunks)
    for index, chunk in enumerate(chunks, start=1):
        clip_path = clips_dir / f"{chunk['id']}.mp3"
        text = str(chunk["rewritten"]).strip()
        print(f"  [{index}/{total}] {chunk['id']}")
        await _synthesize_clip(text, voice, clip_path)
        if index < total:
            await asyncio.sleep(_GAP_SECONDS)


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

    asyncio.run(_synthesize_all(chunks, selected_voice, paths.clips_dir))

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
