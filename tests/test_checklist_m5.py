from __future__ import annotations

from datetime import datetime, timezone

import os
import pytest
from fastapi.testclient import TestClient

from personal_ops_agent.checklist.generator import generate_checklist
from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.graph.build import build_graph
from personal_ops_agent.main import app


def _calendar(title: str, location: str = "Office") -> dict:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return {
        "events": [
            {
                "id": "evt-1",
                "title": title,
                "start": now.isoformat(),
                "end": (now.replace(hour=(now.hour + 1) % 24)).isoformat(),
                "location": location,
            }
        ]
    }


def _weather(rain: int, temp: float) -> dict:
    return {"points": [{"rain_probability": rain, "apparent_temperature": temp, "wind_kph": 10.0}]}


def _commute(mode: str) -> dict:
    return {"recommendation": {"transport_mode": mode, "leave_time": "2026-01-01T08:00:00+00:00"}}


@pytest.mark.parametrize(
    ("title", "rain", "temp", "mode", "must_have"),
    [
        ("Weekly sync", 60, 10.0, "walk", "Umbrella"),
        ("Client meeting", 10, 0.0, "walk", "Warm coat and gloves"),
        ("Office visit", 10, 8.0, "transit", "Transit card / ride-share app ready"),
        ("presentation prep", 10, 8.0, "walk", "Laptop and charger"),
        ("interview loop", 10, 8.0, "walk", "ID / badge"),
        ("exam center", 55, 1.0, "taxi", "Umbrella"),
        ("exam center", 55, 1.0, "taxi", "Warm coat and gloves"),
        ("exam center", 55, 1.0, "taxi", "Transit card / ride-share app ready"),
        ("presentation day", 55, 1.0, "taxi", "Laptop and charger"),
        ("interview day", 55, 1.0, "taxi", "ID / badge"),
    ],
)
def test_checklist_scenarios(title: str, rain: int, temp: float, mode: str, must_have: str) -> None:
    checklist = generate_checklist(
        trace_id="test",
        calendar_state=_calendar(title),
        weather_state=_weather(rain, temp),
        commute_state=_commute(mode),
    )
    assert checklist.summary
    assert checklist.items
    assert checklist.reasons
    assert len(checklist.items) == len(checklist.reasons)
    assert must_have in checklist.items


def test_checklist_intent_flow_smoke() -> None:
    os.environ["APP_ENV"] = "test"
    os.environ["LOG_LEVEL"] = "INFO"
    os.environ["MOCK_CALENDAR"] = "1"
    os.environ["GOOGLE_CALENDAR_MODE"] = "mock"
    os.environ["CALENDAR_FIXTURE_PATH"] = "tests/fixtures/sample_calendar.json"
    os.environ["MOCK_WEATHER"] = "1"
    os.environ["WEATHER_MODE"] = "mock"
    os.environ["WEATHER_FIXTURE_PATH"] = "tests/fixtures/sample_weather.json"
    os.environ["MOCK_ETA"] = "1"
    os.environ["ETA_PROVIDER"] = "mock"
    os.environ["ETA_MODE"] = "mock"
    os.environ["ETA_FIXTURE_PATH"] = "tests/fixtures/sample_eta.json"
    get_settings.cache_clear()
    build_graph.cache_clear()

    client = TestClient(app)
    response = client.post("/chat", json={"message": "what should I bring for my next event"})
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "leaving_checklist"
    assert "checklist" in body["state"]
    assert body["state"]["checklist"]["items"]
