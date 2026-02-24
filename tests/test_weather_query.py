import os

from fastapi.testclient import TestClient

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.graph.build import build_graph
from personal_ops_agent.main import app


def _setup_env() -> None:
    os.environ["APP_ENV"] = "test"
    os.environ["LOG_LEVEL"] = "INFO"
    os.environ["MOCK_CALENDAR"] = "1"
    os.environ["GOOGLE_CALENDAR_MODE"] = "mock"
    os.environ["MOCK_WEATHER"] = "1"
    os.environ["WEATHER_MODE"] = "mock"
    os.environ["WEATHER_FIXTURE_PATH"] = "tests/fixtures/sample_weather.json"
    os.environ["DEFAULT_TIMEZONE"] = "America/New_York"
    os.environ["TIMEWINDOW_NOW_ISO"] = "2026-01-15T08:10:00-05:00"


def test_weather_query_today() -> None:
    _setup_env()
    get_settings.cache_clear()
    build_graph.cache_clear()
    client = TestClient(app)

    response = client.post("/chat", json={"message": "今天天气怎么样"})
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "weather_summary"
    assert "weather" in body["state"]
    assert isinstance(body["state"]["weather"]["summary"], str)
    assert body["state"]["weather"]["window_source"] in {"rule", "llm", "default"}


def test_weather_query_specific_period() -> None:
    _setup_env()
    get_settings.cache_clear()
    build_graph.cache_clear()
    client = TestClient(app)

    response = client.post("/chat", json={"message": "明天下午天气怎么样"})
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "weather_summary"
    window_start = body["state"]["weather"]["window_start"]
    window_end = body["state"]["weather"]["window_end"]
    assert window_start < window_end
