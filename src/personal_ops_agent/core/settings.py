from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    APP_ENV: Literal["development", "test", "staging", "production"]
    LOG_LEVEL: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
    OPENAI_API_KEY: str | None = None
    MOCK_CALENDAR: bool = False
    GOOGLE_CALENDAR_MODE: Literal["mock", "oauth"] = "mock"
    GOOGLE_CALENDAR_ID: str = "primary"
    GOOGLE_OAUTH_CLIENT_SECRET_JSON: str | None = None
    GOOGLE_OAUTH_TOKEN_JSON: str | None = None
    CALENDAR_FIXTURE_PATH: str = "tests/fixtures/sample_calendar.json"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
