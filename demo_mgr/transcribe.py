"""Transcription with faster-whisper."""

from __future__ import annotations

import json
import os
from pathlib import Path

from faster_whisper import WhisperModel

from demo_mgr.chunks import merge_segments
from demo_mgr.ffmpeg_util import extract_audio, probe_duration
from demo_mgr.paths import DemoPaths, demo_paths, find_source_video, resolve_demo_dir


def transcribe_demo(
    demo_dir_path: str | Path,
    *,
    model_name: str | None = None,
    input_path: str | Path | None = None,
    force: bool = False,
) -> DemoPaths:
    demo_dir = resolve_demo_dir(demo_dir_path)
    source = find_source_video(demo_dir, input_path)
    paths = demo_paths(demo_dir, source)

    if paths.transcript.exists() and paths.script.exists() and not force:
        print(f"Skipping transcribe (outputs exist). Use --force to rerun: {paths.demo_dir}")
        return paths

    print(f"Extracting audio from {paths.source.name}...")
    extract_audio(paths.source, paths.audio)

    whisper_model = model_name or os.getenv("WHISPER_MODEL", "small")
    print(f"Transcribing with faster-whisper model '{whisper_model}' (first run downloads weights)...")
    model = WhisperModel(whisper_model, device="cpu", compute_type="int8")

    segments_iter, info = model.transcribe(
        str(paths.audio),
        language="en",
        vad_filter=True,
        word_timestamps=True,
    )

    raw_segments: list[dict[str, object]] = []
    for segment in segments_iter:
        words = []
        if segment.words:
            words = [
                {"word": word.word, "start": round(word.start, 3), "end": round(word.end, 3)}
                for word in segment.words
            ]
        raw_segments.append(
            {
                "start": round(segment.start, 3),
                "end": round(segment.end, 3),
                "text": segment.text.strip(),
                "words": words,
            }
        )

    merged = merge_segments(raw_segments)
    video_duration = probe_duration(paths.source)

    transcript_payload = {
        "source": paths.source.name,
        "model": whisper_model,
        "language": info.language,
        "language_probability": round(info.language_probability, 4),
        "video_duration": round(video_duration, 3),
        "segments": raw_segments,
        "chunks": merged,
    }
    paths.transcript.write_text(json.dumps(transcript_payload, indent=2), encoding="utf-8")

    script_payload = {
        "source": paths.source.name,
        "video_duration": round(video_duration, 3),
        "model": whisper_model,
        "chunks": merged,
    }
    paths.script.write_text(json.dumps(script_payload, indent=2), encoding="utf-8")

    print(f"Wrote {len(raw_segments)} segments -> {len(merged)} chunks")
    print(f"  transcript: {paths.transcript}")
    print(f"  script:     {paths.script}")
    return paths
