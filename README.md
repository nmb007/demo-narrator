# Demo Narrator

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

Turn a rough screen recording into a polished demo video with professional narration.

You record the demo yourself (speaking as you go). English is not required — speak in any language. Whisper turns that speech into English, and the finished video is always with English narration.

This API:

1. **Transcribes** your speech with local Whisper (timestamps included)
2. **Rewrites** each chunk into clear English via Groq
3. **Speaks** the rewrite with Edge TTS
4. **Aligns** the new voice to when you originally spoke
5. **Muxes** the new audio onto your video with ffmpeg

## Prerequisites

- Docker and Docker Compose
- Free [Groq API key](https://console.groq.com) (rewrite step)
- Outbound internet (Groq + Edge TTS; Whisper runs locally in the worker)

## Setup

```bash
cp .env.example .env
# set GROQ_API_KEY and AUTH_JWT_SECRET
docker compose up --build
```

Compose bind-mounts `src/`, `migrations/`, and `tests/` into the containers. The API runs with `--reload`; the worker restarts on Python changes under `src/`. Rebuild (`--build`) only when dependencies or the Dockerfile change.

API: `http://localhost:8000`  
Docs (local/staging): `http://localhost:8000/docs`

### Storage

| Environment | Config |
|-------------|--------|
| Local (default) | `STORAGE_URL=file:///app/storage` (compose mounts `./storage`) |
| Supabase / S3 | `STORAGE_URL=s3://<bucket>` plus `STORAGE_S3_ENDPOINT`, `STORAGE_S3_REGION`, `STORAGE_S3_ACCESS_KEY_ID`, `STORAGE_S3_SECRET_ACCESS_KEY` |

## API flow

All endpoints are under `/v1` and (except signup/login) require `Authorization: Bearer <token>`.

### 1. Sign up

```bash
curl -s -X POST http://localhost:8000/v1/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"password123"}'
```

### 2. Log in

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/login \
  -d 'username=you@example.com&password=password123' | jq -r .access_token)
```

### 3. Narrate (upload)

Limits: **100 MB**, duration **2s–10 minutes**, `.mov` or `.mp4` only. Upload and validation are synchronous; the pipeline runs on Celery.

```bash
curl -s -X POST http://localhost:8000/v1/narrate \
  -H "Authorization: Bearer $TOKEN" \
  -F "video=@./my-recording.mov" \
  -F "voice=en-US-AndrewNeural"
```

Returns `202` with `run_id` and `video_id`.

### 4. Poll run status

```bash
curl -s http://localhost:8000/v1/runs/$RUN_ID \
  -H "Authorization: Bearer $TOKEN"
```

### 5. Retry steps

```bash
curl -s -X POST http://localhost:8000/v1/retry \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"video_id\":\"$VIDEO_ID\",\"steps\":[\"voice\",\"mux\"],\"voice\":\"en-US-JennyNeural\"}"
```

Omit `steps` to re-run the full pipeline. Omitting `model` / `voice` / `max_atempo` reuses the previous run’s options.

### 6. Download

```bash
curl -L -o final.mp4 \
  -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/videos/$VIDEO_ID/download
```

## Pipeline steps

| Step | Purpose |
|------|---------|
| `transcribe` | Extract audio + Whisper |
| `rewrite` | Groq rewrite of chunks |
| `voice` | Edge TTS + alignment |
| `mux` | Replace video audio |

The newest `NARRATION_KEEP_FINALS` (default 2) output videos are kept per source video.

## Tests

Tests run in Docker via a separate multi-stage image (`target: test`). The `api` / `worker` images use `target: runtime` and do not include `tests/` or the `dev` dependency group.

```bash
docker compose --profile test run --rm test
```

Useful variants:

```bash
docker compose --profile test run --rm test uv run pytest -q
docker compose --profile test run --rm test uv run pytest tests/test_auth.py
docker compose --profile test run --rm test uv run pytest -k signup
```

Test Coverage:

```bash
docker compose --profile test run --rm test uv run pytest --cov=src --cov-report=term-missing
```

`docker compose up` does not start the `test` service (it is behind the `test` profile). Tests use an in-memory SQLite database in-process, so they do not need Postgres/Redis and do not write to your Compose database.

## Stack

- Python 3.14, FastAPI, uv
- Postgres + SQLModel + Alembic
- Celery + Redis
- obstore (local `file://` or S3-compatible object storage)
- faster-whisper, Groq, edge-tts, ffmpeg

## License

This project is licensed under the [MIT License](LICENSE).
