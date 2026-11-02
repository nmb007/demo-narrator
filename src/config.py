"""Global application settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: str = "local"
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/narrator"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    # Comma-separated browser origins. Empty means no cross-origin browser calls.
    CORS_ALLOW_ORIGINS: str = "http://localhost:3000"


settings = Settings()


def cors_allow_origins() -> list[str]:
    return [origin.strip() for origin in settings.CORS_ALLOW_ORIGINS.split(",") if origin.strip()]
