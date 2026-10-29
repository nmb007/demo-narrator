"""Shared persistence base models."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class UUIDModel(SQLModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True)


class TimestampModel(SQLModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
