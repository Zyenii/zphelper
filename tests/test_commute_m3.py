import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "INFO")

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.graph.build import build_graph
from personal_ops_agent.main import app


def _set_base_env() -> None:
    os.environ["APP_ENV"] = "test"
    os.environ["LOG_LEVEL"] = "INFO"
    os.environ["MOCK_CALENDAR"] = "1"
    os.environ["GOOGLE_CALENDAR_MODE"] = "mock"
    os.environ["CALENDAR_FIXTURE_PATH"] = "tests/fixtures/sample_calendar.json"
    os.environ["MOCK_WEATHER"] = "1"
    os.environ["WEATHER_MODE"] = "mock"
    os.environ["MOCK_ETA"] = "1"
    os.environ["ETA_MODE"] = "mock"
    os.environ["COMMUTE_NOW_ISO"] = "2026-01-15T08:10:00+00:00"


@pytest.mark.parametrize(
    ("weather_fixture", "eta_fixture", "expected_mode"),
    [
        ("tests/fixtures/weather_sunny.json", "tests/fixtures/eta_sunny.json", "walk"),
        ("tests/fixtures/weather_rainy.json", "tests/fixtures/eta_rainy.json", "taxi"),
        ("tests/fixtures/weather_peak.json", "tests/fixtures/eta_peak.json", "transit"),
    ],
)
def test_commute_scenarios(weather_fixture: str, eta_fixture: str, expected_mode: str) -> None:
    _set_base_env()
    os.environ["WEATHER_FIXTURE_PATH"] = weather_fixture
    os.environ["ETA_FIXTURE_PATH"] = eta_fixture

    get_settings.cache_clear()
    build_graph.cache_clear()

    client = TestClient(app)
    response = client.post("/chat", json={"message": "我几点出发去下一个日程？"})
    assert response.status_code == 200
    body = response.json()

    assert body["intent"] == "commute_advice"
    assert "weather" in body["state"]
    assert isinstance(body["state"]["weather"]["summary"], str)
    assert "commute" in body["state"]
    recommendation = body["state"]["commute"]["recommendation"]
    assert recommendation["transport_mode"] == expected_mode
    assert recommendation["leave_time"]
    assert recommendation["weather_advice"]
    assert recommendation["explanation"]
    assert recommendation["eta_minutes"] > 0
    assert recommendation["buffer_minutes"] > 0
