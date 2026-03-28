from __future__ import annotations

from functools import lru_cache
import os
from typing import Literal

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    APP_ENV: Literal["development", "test", "staging", "production"]
    LOG_LEVEL: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
    PREFER_DOTENV_IN_DEV: bool = True
    OPENAI_API_KEY: str | None = None
    OPENAI_INPUT_COST_PER_1K_USD: float = 0.0
    OPENAI_OUTPUT_COST_PER_1K_USD: float = 0.0
    LLM_ROUTER: bool = False
    LLM_ROUTER_MODEL: str = "gpt-4.1-mini"
    LLM_ROUTER_THRESHOLD: float = 0.7
    LLM_ROUTER_RETRIES: int = 1
    LLM_PLANNER: bool = False
    LLM_PLANNER_MODEL: str = "gpt-5-mini"
    LLM_PLANNER_THRESHOLD: float = 0.75
    LLM_PLANNER_MAX_ACTIONS: int = 4
    UNKNOWN_LLM_REPLY: bool = False
    UNKNOWN_LLM_MODEL: str = "gpt-5-mini"
    LLM_TIMEWINDOW: bool = False
    LLM_TIMEWINDOW_MODEL: str = "gpt-5-mini"
    LLM_TIMEWINDOW_THRESHOLD: float = 0.75
    LLM_LOCATION_EXTRACTOR: bool = False
    LLM_LOCATION_EXTRACTOR_MODEL: str = "gpt-5-mini"
    LLM_LOCATION_EXTRACTOR_THRESHOLD: float = 0.75
    LLM_CALENDAR_CREATE_TIME: bool = False
    LLM_CALENDAR_CREATE_MODEL: str = "gpt-5-mini"
    LLM_CALENDAR_CREATE_THRESHOLD: float = 0.75
    TODO_PARSER_MODEL: str = "gpt-5-mini"
    TODO_CONFIDENCE_THRESHOLD: float = 0.7
    TODO_PARSE_RETRIES: int = 2
    CHECKLIST_MODEL: str = "gpt-5-mini"
    CHECKLIST_CONFIDENCE_THRESHOLD: float = 0.7
    CHECKLIST_RETRIES: int = 2
    PROMPT_VERSION: str = "v1"
    DATABASE_URL: str | None = None
    TODOIST_API_TOKEN: str | None = None
    DEFAULT_TIMEZONE: str = "America/New_York"
    MEMORY_ENABLED: bool = True
    MEMORY_STORE_PATH: str = "data/user_memory.json"
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

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        app_env = os.getenv("APP_ENV", "development").lower()
        prefer_dotenv = os.getenv("PREFER_DOTENV_IN_DEV", "1") == "1"
        if app_env == "development" and prefer_dotenv:
            return (init_settings, dotenv_settings, env_settings, file_secret_settings)
        return (init_settings, env_settings, dotenv_settings, file_secret_settings)


@lru_cache
def get_settings() -> Settings:
    return Settings()
