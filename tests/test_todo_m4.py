import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "INFO")

from personal_ops_agent.main import app


def test_todo_intent_returns_clarification_on_low_confidence() -> None:
    os.environ["TODO_CONFIDENCE_THRESHOLD"] = "0.7"
    os.environ["OPENAI_API_KEY"] = ""
    client = TestClient(app)
    response = client.post("/chat", json={"message": "提醒我明天交作业"})
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "todo_create"
    assert body["state"]["todo"]["write"]["blocked_by_confidence"] is True
    assert "clarification_question" in body["state"]["todo"]["write"]


def test_todo_eval_fixture_cases_schema_valid() -> None:
    fixture_path = Path("tests/fixtures/todo_m4_cases.json")
    cases = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert len(cases) == 10
