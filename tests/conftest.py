"""Shared test fixtures."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

os.environ["ENVIRONMENT"] = "local"
os.environ["AUTH_JWT_SECRET"] = "test-secret-at-least-32-characters-long"
os.environ["STORAGE_URL"] = "memory://"
# Engines are constructed at import time; tests replace sync sessions with SQLite.
os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres@localhost:5432/narrator"
os.environ["CELERY_BROKER_URL"] = "memory://"
os.environ["NARRATION_MAX_UPLOAD_BYTES"] = "104857600"
os.environ["NARRATION_MAX_DURATION_SECONDS"] = "600"
os.environ["NARRATION_MIN_DURATION_SECONDS"] = "2"

from src.auth import models as auth_models  # noqa: E402,F401
from src.auth import service as auth_service  # noqa: E402
from src.main import app  # noqa: E402
from src.narration import models as narration_models  # noqa: E402,F401
from src.narration import service as narration_service  # noqa: E402
from src.storage import service as storage_service  # noqa: E402
from src.storage.config import storage_settings  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_storage(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(storage_settings, "URL", "memory://")
    storage_service.reset_store()
    yield
    storage_service.reset_store()


@pytest.fixture(autouse=True)
def _sync_db(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    @contextmanager
    def get_session():
        with Session(engine) as session:
            yield session

    monkeypatch.setattr(narration_service, "get_sync_session", get_session)
    monkeypatch.setattr(auth_service, "get_sync_session", get_session)
    try:
        yield
    finally:
        # StaticPool keeps the in-memory SQLite connection alive; close it
        # so pytest does not report ResourceWarning: unclosed database.
        engine.dispose()


@pytest.fixture(autouse=True)
def _stub_celery(monkeypatch: pytest.MonkeyPatch) -> None:
    enqueued: list[str] = []

    def fake_enqueue(run_id) -> None:
        enqueued.append(str(run_id))

    monkeypatch.setattr(narration_service, "enqueue_run", fake_enqueue)
    app.state.enqueued_runs = enqueued  # type: ignore[attr-defined]


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
