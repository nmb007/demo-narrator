"""Database engines and session factories."""

from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import Session, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from src.config import settings

POSTGRES_INDEXES_NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}

metadata = MetaData(naming_convention=POSTGRES_INDEXES_NAMING_CONVENTION)

from sqlmodel import SQLModel  # noqa: E402

SQLModel.metadata.naming_convention = POSTGRES_INDEXES_NAMING_CONVENTION

# Register domain models on metadata for Alembic / create_all.
from src.auth.models import User  # noqa: E402,F401
from src.narration.models import NarrationRun, Video  # noqa: E402,F401

async_engine = create_async_engine(settings.DATABASE_URL, echo=False)
sync_engine = create_engine(settings.DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


@contextmanager
def get_sync_session() -> Generator[Session]:
    with Session(sync_engine) as session:
        yield session
