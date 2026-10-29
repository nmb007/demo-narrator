"""Transcription with faster-whisper."""

from __future__ import annotations

import json

from faster_whisper import WhisperModel

from src.narration.config import narration_settings
from src.narration.pipeline.chunks import merge_segments
from src.narration.pipeline.ffmpeg_util import extract_audio, probe_duration
from src.narration.pipeline.paths import WorkPaths


def transcribe_video(
    paths: WorkPaths,
    *,
    model_name: str | None = None,
    force: bool = False,
) -> WorkPaths:
    if paths.transcript.exists() and paths.script.exists() and not force:
        print(f"Skipping transcribe (outputs exist): {paths.work_dir}")
        return paths

    print(f"Extracting audio from {paths.source.name}...")
    extract_audio(paths.source, paths.audio)

    whisper_model = model_name or narration_settings.WHISPER_MODEL
    print(f"Transcribing with faster-whisper model '{whisper_model}'...")
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
                {
                    "word": word.word,
                    "start": round(word.start, 3),
                    "end": round(word.end, 3),
                }
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
    return paths
