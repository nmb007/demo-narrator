# --- shared base ---
FROM python:3.14-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-install-project --no-dev

COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./

# --- production / default (api + worker) ---
FROM base AS runtime
RUN uv sync --locked --no-dev
CMD ["fastapi", "run", "--host", "0.0.0.0", "--port", "8000"]

# --- tests only ---
FROM base AS test
COPY tests ./tests
RUN uv sync --locked --group dev
CMD ["uv", "run", "pytest"]
