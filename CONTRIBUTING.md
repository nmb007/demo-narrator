# Contributing to Demo Narrator

Thanks for taking an interest in the project. Direct pushes to `main` are not available — please use a fork and a pull request.

## How to contribute

1. Fork the repository.
2. Clone your fork and create a branch from `main`.
3. Make your change.
4. Open a pull request against `nmb007/demo-narrator`.

Please keep pull requests focused: one issue or feature per PR.

## Local setup

```bash
git clone https://github.com/<your-username>/demo-narrator.git
cd demo-narrator
cp .env.example .env
# Add GROQ_API_KEY to .env
docker compose build
```

Do not commit `.env`, API keys, source videos, or generated artifacts (`audio.wav`, `clips/`, `narration.wav`, `final.mp4`).

## Issues

Bug reports and feature ideas are welcome via [GitHub Issues](https://github.com/nmb007/demo-narrator/issues).

When reporting a bug, include:

- The command you ran
- The relevant part of the output
- OS and Docker version if it looks environment-related
- Whether `script.json` / `sync-report.json` show anything useful (omit private demo content)
