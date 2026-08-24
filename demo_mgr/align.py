"""Time-align TTS clips to original speech windows."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from pydub import AudioSegment

from demo_mgr.ffmpeg_util import apply_atempo, convert_to_wav, probe_duration
from demo_mgr.paths import DemoPaths


def _chunk_window(chunks: list[dict], index: int, video_duration: float, gap_ms: int = 50) -> float:
    start = float(chunks[index]["start"])
    if index + 1 < len(chunks):
        next_start = float(chunks[index + 1]["start"])
        return max(0.05, next_start - start - (gap_ms / 1000.0))
    return max(0.05, video_duration - start)


def align_narration(paths: DemoPaths, *, max_atempo: float = 1.20) -> dict:
    script = json.loads(paths.script.read_text(encoding="utf-8"))
    chunks = script.get("chunks", [])
    video_duration = float(script.get("video_duration") or probe_duration(paths.source))

    bed_ms = int(round(video_duration * 1000))
    narration = AudioSegment.silent(duration=bed_ms)

    report_rows: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="demo-mgr-align-") as tmp_dir:
        tmp = Path(tmp_dir)
        for index, chunk in enumerate(chunks):
            chunk_id = chunk["id"]
            clip_mp3 = paths.clips_dir / f"{chunk_id}.mp3"
            if not clip_mp3.is_file():
                raise FileNotFoundError(f"Missing TTS clip: {clip_mp3}")

            tts_duration = probe_duration(clip_mp3)
            original_duration = float(chunk["end"]) - float(chunk["start"])
            window = _chunk_window(chunks, index, video_duration)
            start_ms = int(round(float(chunk["start"]) * 1000))

            atempo = 1.0
            status = "ok"
            working_mp3 = clip_mp3

            if tts_duration > window:
                needed_speed = tts_duration / window
                atempo = min(max(needed_speed, 1.0), max_atempo)
                sped_mp3 = tmp / f"{chunk_id}_sped.mp3"
                apply_atempo(clip_mp3, sped_mp3, atempo)
                working_mp3 = sped_mp3
                tts_duration = probe_duration(working_mp3)
                status = "sped" if tts_duration <= window else "warn"

            clip_wav = tmp / f"{chunk_id}.wav"
            convert_to_wav(working_mp3, clip_wav)
            clip_audio = AudioSegment.from_wav(clip_wav)
            narration = narration.overlay(clip_audio, position=start_ms)

            report_rows.append(
                {
                    "id": chunk_id,
                    "start": round(float(chunk["start"]), 3),
                    "original_duration": round(original_duration, 3),
                    "tts_duration": round(tts_duration, 3),
                    "window": round(window, 3),
                    "atempo": round(atempo, 3),
                    "status": status,
                }
            )

    paths.narration.parent.mkdir(parents=True, exist_ok=True)
    narration.export(str(paths.narration), format="wav")

    return {
        "source": paths.source.name,
        "video_duration": round(video_duration, 3),
        "voice": script.get("voice"),
        "max_atempo": max_atempo,
        "chunks": report_rows,
    }
