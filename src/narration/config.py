"""Narration domain settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NarrationConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NARRATION_", env_file=".env", extra="ignore")

    KEEP_FINALS: int = Field(default=2, ge=1)
    MAX_UPLOAD_BYTES: int = Field(default=104_857_600)
    MAX_DURATION_SECONDS: int = Field(default=600)
    MIN_DURATION_SECONDS: int = Field(default=2)
    WHISPER_MODEL: str = "small"
    DEFAULT_VOICE: str = "en-US-AndrewNeural"


narration_settings = NarrationConfig()
