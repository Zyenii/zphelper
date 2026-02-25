import os
from datetime import datetime, time, timedelta, timezone

from fastapi.testclient import TestClient

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "INFO")

from personal_ops_agent.connectors.google_calendar import NormalizedCalendarEvent
from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.graph.build import build_graph
from personal_ops_agent.main import app


def _reset_runtime() -> None:
    get_settings.cache_clear()
    build_graph.cache_clear()


def test_oauth_mode_missing_config_returns_readable_error() -> None:
    os.environ["MOCK_CALENDAR"] = "0"
    os.environ["GOOGLE_CALENDAR_MODE"] = "oauth"
    os.environ["GOOGLE_OAUTH_CLIENT_SECRET_JSON"] = ""
    os.environ["GOOGLE_OAUTH_TOKEN_JSON"] = ""
    _reset_runtime()

    client = TestClient(app)
    response = client.post("/chat", json={"message": "calendar today"})
    assert response.status_code == 200

    body = response.json()
    assert body["intent"] == "schedule_summary"
    assert "Unable to read calendar" in body["output"]
    assert body["state"]["calendar"]["events"] == []
    assert body["state"]["schedule"]["buffer_suggestions"] == []


def test_oauth_mode_success_path_with_monkeypatch(monkeypatch) -> None:
    os.environ["MOCK_CALENDAR"] = "0"
    os.environ["GOOGLE_CALENDAR_MODE"] = "oauth"
    os.environ["GOOGLE_OAUTH_CLIENT_SECRET_JSON"] = "fake-client-secret.json"
    os.environ["GOOGLE_OAUTH_TOKEN_JSON"] = "fake-token.json"
    _reset_runtime()

    today = datetime.now(timezone.utc).date()
    base = datetime.combine(today, time(hour=9), tzinfo=timezone.utc)

    def _fake_oauth_reader(*_args, **_kwargs):
        return [
            NormalizedCalendarEvent(
                id="a",
                title="Standup",
                start=base.isoformat(),
                end=(base + timedelta(hours=1)).isoformat(),
                timezone="UTC",
            ),
            NormalizedCalendarEvent(
                id="b",
                title="Review",
                start=(base + timedelta(hours=1, minutes=5)).isoformat(),
                end=(base + timedelta(hours=1, minutes=45)).isoformat(),
                timezone="UTC",
            ),
        ]

    monkeypatch.setattr(
        "personal_ops_agent.connectors.google_calendar._read_google_events_oauth",
        _fake_oauth_reader,
    )

    client = TestClient(app)
    response = client.post("/chat", json={"message": "what's my agenda today?"})
    assert response.status_code == 200

    body = response.json()
    assert body["intent"] == "schedule_summary"
    assert len(body["state"]["calendar"]["events"]) == 2
    assert body["state"]["schedule"]["summary"].startswith("You have 2 event(s):")
    assert len(body["state"]["schedule"]["buffer_suggestions"]) >= 1
