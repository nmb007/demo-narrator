"""Auth persistence models."""

from sqlmodel import Field

from src.models import TimestampModel, UUIDModel


class User(UUIDModel, TimestampModel, table=True):
    __tablename__ = "user"

    email: str = Field(unique=True, index=True, max_length=320)
    hashed_password: str = Field(max_length=255)
