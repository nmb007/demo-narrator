"""Merge Whisper segments into pause-bounded chunks."""

from __future__ import annotations

from typing import Any


def merge_segments(
    segments: list[dict[str, Any]],
    gap_threshold: float = 0.35,
    max_chunk_duration: float = 12.0,
) -> list[dict[str, Any]]:
    if not segments:
        return []

    chunks: list[dict[str, Any]] = []
    current_text_parts: list[str] = []
    chunk_start = float(segments[0]["start"])
    chunk_end = float(segments[0]["end"])

    def flush() -> None:
        nonlocal current_text_parts, chunk_start, chunk_end
        text = " ".join(part.strip() for part in current_text_parts if part.strip()).strip()
        if text:
            chunks.append(
                {
                    "id": f"chunk_{len(chunks) + 1:03d}",
                    "start": round(chunk_start, 3),
                    "end": round(chunk_end, 3),
                    "original": text,
                    "rewritten": "",
                }
            )
        current_text_parts = []

    for index, segment in enumerate(segments):
        start = float(segment["start"])
        end = float(segment["end"])
        text = str(segment.get("text", "")).strip()
        if not text:
            continue

        if not current_text_parts:
            chunk_start = start
            chunk_end = end
            current_text_parts.append(text)
            continue

        gap = start - chunk_end
        prospective_duration = end - chunk_start
        if gap <= gap_threshold and prospective_duration <= max_chunk_duration:
            current_text_parts.append(text)
            chunk_end = end
        else:
            flush()
            chunk_start = start
            chunk_end = end
            current_text_parts = [text]

    flush()
    return chunks
