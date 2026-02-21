import os

from fastapi.testclient import TestClient

os.environ["APP_ENV"] = "test"
os.environ["LOG_LEVEL"] = "INFO"
os.environ["MOCK_CALENDAR"] = "1"
os.environ["GOOGLE_CALENDAR_MODE"] = "mock"
os.environ["CALENDAR_FIXTURE_PATH"] = "tests/fixtures/sample_calendar.json"

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.graph.build import build_graph
from personal_ops_agent.main import app


def test_schedule_summary_with_mock_calendar() -> None:
    os.environ["MOCK_CALENDAR"] = "1"
    os.environ["GOOGLE_CALENDAR_MODE"] = "mock"
    os.environ["CALENDAR_FIXTURE_PATH"] = "tests/fixtures/sample_calendar.json"
    os.environ.pop("GOOGLE_OAUTH_CLIENT_SECRET_JSON", None)
    os.environ.pop("GOOGLE_OAUTH_TOKEN_JSON", None)

    get_settings.cache_clear()
    build_graph.cache_clear()

    client = TestClient(app)
    response = client.post("/chat", json={"message": "what's my schedule today?"})

    assert response.status_code == 200
    data = response.json()

    assert "trace_id" in data
    assert data["intent"] == "schedule_summary"
    assert isinstance(data["output"], str) and data["output"]
    assert "calendar" in data["state"]
    assert isinstance(data["state"]["calendar"]["events"], list)
    assert len(data["state"]["calendar"]["events"]) >= 1
    assert "schedule" in data["state"]
    assert isinstance(data["state"]["schedule"]["summary"], str)
    suggestions = data["state"]["schedule"]["buffer_suggestions"]
    assert isinstance(suggestions, list)
    assert suggestions
