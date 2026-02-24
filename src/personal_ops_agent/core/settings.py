from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    APP_ENV: Literal["development", "test", "staging", "production"]
    LOG_LEVEL: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
    OPENAI_API_KEY: str | None = None
    LLM_ROUTER: bool = False
    LLM_ROUTER_MODEL: str = "gpt-4.1-mini"
    LLM_ROUTER_THRESHOLD: float = 0.7
    LLM_TIMEWINDOW: bool = False
    LLM_TIMEWINDOW_MODEL: str = "gpt-5-mini"
    LLM_TIMEWINDOW_THRESHOLD: float = 0.75
    DEFAULT_TIMEZONE: str = "America/New_York"
    TIMEWINDOW_NOW_ISO: str | None = None
    MOCK_CALENDAR: bool = False
    GOOGLE_CALENDAR_MODE: Literal["mock", "oauth"] = "mock"
    GOOGLE_CALENDAR_ID: str = "primary"
    GOOGLE_OAUTH_CLIENT_SECRET_JSON: str | None = None
    GOOGLE_OAUTH_TOKEN_JSON: str | None = None
    CALENDAR_FIXTURE_PATH: str = "tests/fixtures/sample_calendar.json"
    MOCK_WEATHER: bool = True
    WEATHER_MODE: Literal["mock", "open_meteo"] = "mock"
    WEATHER_FIXTURE_PATH: str = "tests/fixtures/sample_weather.json"
    WEATHER_LATITUDE: float = 39.9526
    WEATHER_LONGITUDE: float = -75.1652
    WEATHER_FORECAST_HOURS: int = 6
    MOCK_ETA: bool = True
    ETA_MODE: Literal["mock", "heuristic", "google"] = "mock"
    ETA_PROVIDER: Literal["mock", "heuristic", "google"] = "mock"
    ETA_FIXTURE_PATH: str = "tests/fixtures/sample_eta.json"
    ETA_BASE_MINUTES: int = 30
    ETA_CACHE_TTL_SECONDS: int = 90
    DEFAULT_ORIGIN: str = "Home"
    GOOGLE_ROUTES_API_KEY: str | None = None
    ROUTES_API: str | None = None
    COMMUTE_NOW_ISO: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
