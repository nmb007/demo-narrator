"""Rewrite chunks with Groq."""

from __future__ import annotations

import json
import os
from pathlib import Path

from openai import OpenAI

from demo_mgr.paths import DemoPaths, demo_paths, resolve_demo_dir

REWRITE_SYSTEM_PROMPT = """You rewrite spoken demo transcripts into clear, professional English narration.
Return JSON only with this exact shape:
{"chunks": [{"id": "<id>", "rewritten": "<text>"}]}

Rules:
- Keep roughly the same spoken length (similar word count) so timing still works.
- Do not add steps or features that were not in the original.
- Use present tense and direct, confident demo voice.
- Preserve technical terms and product names exactly when present.
"""


def _build_user_prompt(chunks: list[dict]) -> str:
    payload = [
        {
            "id": chunk["id"],
            "start": chunk["start"],
            "end": chunk["end"],
            "original": chunk.get("original") or chunk.get("text", ""),
        }
        for chunk in chunks
    ]
    return (
        "Rewrite each chunk as clear professional demo narration.\n\n"
        f"{json.dumps({'chunks': payload}, indent=2)}"
    )


def _parse_rewrite_response(raw: str, chunks: list[dict]) -> list[dict]:
    data = json.loads(raw)
    rewritten_by_id = {
        item["id"]: str(item.get("rewritten", "")).strip()
        for item in data.get("chunks", [])
        if item.get("id")
    }
    updated = []
    for chunk in chunks:
        updated_chunk = dict(chunk)
        rewritten = rewritten_by_id.get(chunk["id"], "").strip()
        if rewritten:
            updated_chunk["rewritten"] = rewritten
        elif not updated_chunk.get("rewritten"):
            updated_chunk["rewritten"] = updated_chunk.get("original", "")
        updated.append(updated_chunk)
    return updated


def rewrite_demo(
    demo_dir_path: str | Path,
    *,
    force: bool = False,
) -> DemoPaths:
    demo_dir = resolve_demo_dir(demo_dir_path)
    paths = demo_paths(demo_dir)

    if not paths.script.exists():
        raise FileNotFoundError(f"Missing script.json. Run transcribe first: {paths.script}")

    script = json.loads(paths.script.read_text(encoding="utf-8"))
    chunks = script.get("chunks", [])
    if not chunks:
        raise ValueError(f"No chunks found in {paths.script}")

    already_rewritten = all(chunk.get("rewritten") for chunk in chunks)
    if already_rewritten and not force:
        print(f"Skipping rewrite (script already has rewritten text). Use --force to rerun: {paths.demo_dir}")
        return paths

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY is not set. Copy .env.example to .env and add your key.")

    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

    user_prompt = _build_user_prompt(chunks)
    print(f"Rewriting {len(chunks)} chunks with Groq ({model})...")

    last_error: Exception | None = None
    raw = ""
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            raw = response.choices[0].message.content or ""
            updated_chunks = _parse_rewrite_response(raw, chunks)
            script["chunks"] = updated_chunks
            script["rewrite_model"] = model
            paths.script.write_text(json.dumps(script, indent=2), encoding="utf-8")
            print(f"Updated script: {paths.script}")
            return paths
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            last_error = exc
            (paths.demo_dir / "rewrite-raw.txt").write_text(raw, encoding="utf-8")
            print(f"Rewrite parse failed (attempt {attempt + 1}/2): {exc}")

    raise RuntimeError(f"Groq rewrite failed after retries: {last_error}")
