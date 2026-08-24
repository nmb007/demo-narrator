# Demo Manager

Turn a rough screen recording into a polished demo video with professional narration.

You record the demo yourself (speaking as you go). English is not required — speak in any language. Whisper turn that speech into English, and the finished video is always with English narration/audio.

This tool:

1. **Transcribes** your speech with local Whisper (timestamps included)
2. **Rewrites** each chunk into clear English via Groq
3. **Speaks** the rewrite in a new neural voice with Edge TTS
4. **Aligns** the new voice to when you originally spoke
5. **Muxes** the new audio onto your video with ffmpeg

Your original mic audio is replaced. The video stream is copied (not re-encoded), so macOS `.mov` (including HEVC) works fine.

## Prerequisites

- [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)
- Free [Groq API key](https://console.groq.com) (rewrite step)
- Outbound internet (Groq + Edge TTS are cloud calls; Whisper runs locally in the container)

You do **not** need Microsoft Edge, a local Python install, or `brew install ffmpeg` for the default workflow.

## Project layout

```
demo-manager/
  demos/
    login-flow/
      source.mov      # or source.mp4 — your recording (you add this)
      audio.wav       # extracted mono audio
      transcript.json # raw Whisper segments
      script.json     # timed chunks + rewritten text (editable)
      clips/          # one TTS mp3 per chunk
      narration.wav   # full aligned narration track
      sync-report.json
      final.mp4       # finished video
```

## Setup

1. Clone or open this repo.

2. Create your env file:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and set `GROQ_API_KEY`.

3. Build the Docker image:

   ```bash
   docker compose build
   ```

## Run

Create a demo folder and add your recording:

```bash
mkdir -p demos/login-flow
cp ~/Movies/my-demo.mov demos/login-flow/source.mov
```

Run the full pipeline:

```bash
docker compose run --rm demo-mgr run demos/login-flow
```

Or run steps individually:

```bash
docker compose run --rm demo-mgr transcribe demos/login-flow
docker compose run --rm demo-mgr rewrite demos/login-flow
docker compose run --rm demo-mgr voice demos/login-flow
docker compose run --rm demo-mgr mux demos/login-flow
```

### Useful flags

| Flag | Description |
|------|-------------|
| `--force` | Re-run a step even if outputs already exist |
| `--input path/to/video.mov` | Use a specific source file (Default is source.mov or source.mp4) |
| `--model medium` | Larger Whisper model (more accurate, slower) |
| `--voice en-US-JennyNeural` | Pick a different Edge TTS voice |
| `--max-atempo 1.20` | Max speed-up when TTS is longer than its time window |

Examples:

```bash
docker compose run --rm demo-mgr run demos/login-flow --model medium
docker compose run --rm demo-mgr voice demos/login-flow --voice en-US-JennyNeural --force
docker compose run --rm demo-mgr transcribe demos/login-flow --input demos/login-flow/my-custom-video.mp4
```

Open a shell inside the container:

```bash
docker compose run --rm --entrypoint bash demo-mgr
python -m demo_mgr --help
```

## Input formats

| Source | Typical origin |
|--------|----------------|
| `source.mov` | macOS Screenshot / QuickTime |
| `source.mp4` | OBS or other recorders |

If both exist, `source.mov` is used unless you pass `--input`.

Output is always `final.mp4` (video copied, new AAC audio).

## How voices work

Edge TTS uses Microsoft's cloud neural voices. No Edge browser install is required — the Python `edge-tts` library sends text over HTTPS and saves MP3 clips.

- Default voice: `en-US-AndrewNeural`
- List voices: `docker compose run --rm demo-mgr bash -lc "edge-tts --list-voices | grep en-US"`
- The **rewritten** script is spoken in this new voice, not your recorded mic

Whisper only uses your recording to capture **what you said and when**. Groq improves the words. Edge TTS narrates them. Alignment places each sentence where you originally spoke.

## Recording tips

- Speak through the demo — Whisper needs your voice for timestamps
- Pause ~0.5s after important clicks; pauses become alignment anchors
- Don't worry about grammar or mic quality; both get replaced
- v1 replaces **all** audio (no mix of TTS + system sounds)

## Editing the script

If you want to change the Grok output that will eventually will be converted into audio.
You can open `demos/<name>/script.json` and edit any `rewritten` field. Then regenerate voice and mux only:

```bash
docker compose run --rm demo-mgr voice demos/login-flow --force
docker compose run --rm demo-mgr mux demos/login-flow --force
```

## How sync works

This is **timeline sync**, not lip-sync. The video clock never changes.

For each chunk, TTS is placed at the original speech `start` time. If the new clip is longer than the gap until the next chunk, it is sped up (up to 1.20×). Check `sync-report.json` for per-chunk status: `ok`, `sped`, or `warn`.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `No source video found` | Add `source.mov` or `source.mp4` to the demo folder |
| `GROQ_API_KEY is not set` | Copy `.env.example` → `.env` and add your key |
| Groq `model_not_found` | Set `GROQ_MODEL` in `.env` to a current Groq model (default is `openai/gpt-oss-120b`) |
| First transcribe is slow | Whisper downloads ~500MB model into the `whisper-cache` Docker volume |
| Edge TTS fails | Container needs outbound network |
| HEVC `.mov` won't play somewhere | `final.mp4` uses stream copy; re-encode separately if a player lacks HEVC |
| Rewrite returns bad JSON | See `rewrite-raw.txt` in the demo folder; re-run with `--force` |

## Stack

- Python 3.11 CLI in Docker
- ffmpeg / ffprobe
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — local transcription
- [Groq](https://groq.com) — `openai/gpt-oss-120b` rewrite
- [edge-tts](https://github.com/rany2/edge-tts) — free neural TTS
- pydub — overlay timed audio clips

## License

Use and modify freely for personal demo workflows.
