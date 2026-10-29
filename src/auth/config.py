"""Auth domain settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUTH_", env_file=".env", extra="ignore")

    JWT_SECRET: str = "change-me-in-production"
    JWT_ALG: str = "HS256"
    JWT_EXP_MINUTES: int = 60


auth_settings = AuthConfig()
