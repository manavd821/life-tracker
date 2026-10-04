import logging
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str
    CLERK_WEBHOOK_SECRET: str
    CLERK_ISSUER: str
    CLERK_AUDIENCE: str | None = None
    CLERK_ALLOWED_ORIGINS: list[str] = []

    @field_validator("DATABASE_URL")
    @classmethod
    def use_async_driver(cls, value: str) -> str:
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value


@lru_cache
def get_settings() -> Settings:
    try:
        logger.info("loading environment variables...")
        settings = Settings()
        logger.info("environment variable loaded succesfully")
        return settings
    except Exception as e:
        logger.error("Failed to load environment variables: %s", e)
        raise
