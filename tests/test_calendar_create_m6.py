import os

from fastapi.testclient import TestClient

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "INFO")

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.graph.build import build_graph
from personal_ops_agent.main import app


def _set_mock_calendar_env() -> None:
    os.environ["APP_ENV"] = "test"
    os.environ["LOG_LEVEL"] = "INFO"
    os.environ["MOCK_CALENDAR"] = "1"
    os.environ["GOOGLE_CALENDAR_MODE"] = "mock"
    os.environ["CALENDAR_FIXTURE_PATH"] = "tests/fixtures/sample_calendar.json"
    get_settings.cache_clear()
    build_graph.cache_clear()


def test_calendar_create_idempotent_and_agent_mark() -> None:
    _set_mock_calendar_env()
    client = TestClient(app)
    message = "create event team sync 2026-03-01 10:00 2026-03-01 11:00 at Office"

    first = client.post("/chat", json={"message": message})
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["intent"] == "calendar_create"
    first_write = first_body["state"]["calendar_write"]
    assert first_write["success"] is True
    assert first_write["created"] is True
    assert first_write["summary"].startswith("[Agent]")

    second = client.post("/chat", json={"message": message})
    assert second.status_code == 200
    second_body = second.json()
    second_write = second_body["state"]["calendar_write"]
    assert second_write["success"] is True
    assert second_write["created"] is False
    assert second_write["event_id"] == first_write["event_id"]
