from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "INFO")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("LLM_ROUTER", "0")
os.environ.setdefault("LLM_PLANNER", "0")
os.environ.setdefault("UNKNOWN_LLM_REPLY", "0")

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.graph.build import build_graph
from personal_ops_agent.main import app
from personal_ops_agent.planner.planner import make_plan
from personal_ops_agent.planner.schemas import ExecutionPlan
from personal_ops_agent.router.intent import Intent


def _reset_caches() -> None:
    get_settings.cache_clear()
    build_graph.cache_clear()


def test_planner_low_confidence_returns_none(monkeypatch) -> None:
    os.environ["APP_ENV"] = "test"
    os.environ["LOG_LEVEL"] = "INFO"
    os.environ["OPENAI_API_KEY"] = "test-key"
    os.environ["LLM_PLANNER"] = "1"
    os.environ["LLM_PLANNER_THRESHOLD"] = "0.75"
    _reset_caches()

    monkeypatch.setattr(
        "personal_ops_agent.planner.planner._call_openai_planner",
        lambda *_args, **_kwargs: (
            '{"goal":"check schedule","intent":"schedule_summary","actions":[{"tool":"schedule_read","args":{}},{"tool":"schedule_summarize","args":{}}],"reason":"need schedule","confidence":0.4}'
        ),
    )
    assert make_plan("what is my schedule") is None


def test_planner_unknown_allows_empty_actions(monkeypatch) -> None:
    os.environ["APP_ENV"] = "test"
    os.environ["LOG_LEVEL"] = "INFO"
    os.environ["OPENAI_API_KEY"] = "test-key"
    os.environ["LLM_PLANNER"] = "1"
    _reset_caches()

    monkeypatch.setattr(
        "personal_ops_agent.planner.planner._call_openai_planner",
        lambda *_args, **_kwargs: (
            '{"goal":"unsupported","intent":"unknown","actions":[],"reason":"unsupported request","confidence":0.9}'
        ),
    )
    plan = make_plan("tell me a joke")
    assert plan is not None
    assert plan.intent == Intent.UNKNOWN.value
    assert plan.actions == []


def test_chat_uses_planner_path(monkeypatch) -> None:
    _reset_caches()
    client = TestClient(app)
    monkeypatch.setattr(
        "personal_ops_agent.graph.nodes.planner.make_plan",
        lambda _message: ExecutionPlan(
            goal="summarize schedule",
            intent="schedule_summary",
            actions=[
                {"tool": "schedule_read", "args": {}},
                {"tool": "schedule_summarize", "args": {}},
            ],
            reason="need calendar read and summary",
            confidence=0.91,
        ),
    )
    response = client.post("/chat", json={"message": "what's my schedule today?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "schedule_summary"
    assert payload["state"]["plan_used"] is True
    assert payload["state"]["plan"]["actions"][0]["tool"] == "schedule_read"
    assert payload["state"]["eval"]["planner"]["executed_actions"] == ["schedule_read", "schedule_summarize"]


def test_planner_commute_args_preserve_requested_transport_mode(monkeypatch) -> None:
    _reset_caches()
    client = TestClient(app)
    monkeypatch.setattr(
        "personal_ops_agent.graph.nodes.planner.make_plan",
        lambda _message: ExecutionPlan(
            goal="estimate driving eta to new york",
            intent="eta_query",
            actions=[
                {
                    "tool": "commute_plan",
                    "args": {
                        "destination": "New York",
                        "departure_time": "now",
                        "transport_mode": "driving",
                    },
                }
            ],
            reason="need driving eta",
            confidence=0.95,
        ),
    )
    response = client.post("/chat", json={"message": "开车去纽约要多久"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["plan_used"] is True
    assert payload["state"]["commute"]["recommendation"]["transport_mode"] == "driving"


def test_eta_query_defaults_to_driving_even_without_planner_mode_arg(monkeypatch) -> None:
    _reset_caches()
    client = TestClient(app)
    monkeypatch.setattr(
        "personal_ops_agent.graph.nodes.planner.make_plan",
        lambda _message: ExecutionPlan(
            goal="estimate eta to new york",
            intent="eta_query",
            actions=[
                {
                    "tool": "commute_plan",
                    "args": {
                        "destination": "New York",
                        "departure_time": "now",
                    },
                }
            ],
            reason="need realtime eta",
            confidence=0.95,
        ),
    )
    response = client.post("/chat", json={"message": "现在去纽约要多久"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["plan_used"] is True
    assert payload["state"]["commute"]["recommendation"]["transport_mode"] == "driving"


def test_eta_query_transit_is_normalized_to_driving_when_message_is_ambiguous(monkeypatch) -> None:
    _reset_caches()
    monkeypatch.setattr(
        "personal_ops_agent.planner.planner._call_openai_planner",
        lambda *_args, **_kwargs: (
            '{"goal":"estimate travel time","intent":"eta_query","actions":[{"tool":"commute_plan","args":{"destination":"New York","departure_time":"now","transport_mode":"transit"}}],"reason":"needs eta","confidence":0.9}'
        ),
    )
    os.environ["APP_ENV"] = "test"
    os.environ["LOG_LEVEL"] = "INFO"
    os.environ["OPENAI_API_KEY"] = "test-key"
    os.environ["LLM_PLANNER"] = "1"
    _reset_caches()

    plan = make_plan("现在去纽约交通要多久")
    assert plan is not None
    assert plan.actions[0].args["transport_mode"] == "driving"


def test_eta_query_keeps_transit_when_message_explicitly_requests_transit(monkeypatch) -> None:
    _reset_caches()
    monkeypatch.setattr(
        "personal_ops_agent.planner.planner._call_openai_planner",
        lambda *_args, **_kwargs: (
            '{"goal":"estimate transit time","intent":"eta_query","actions":[{"tool":"commute_plan","args":{"destination":"New York","departure_time":"now","transport_mode":"transit"}}],"reason":"needs transit eta","confidence":0.9}'
        ),
    )
    os.environ["APP_ENV"] = "test"
    os.environ["LOG_LEVEL"] = "INFO"
    os.environ["OPENAI_API_KEY"] = "test-key"
    os.environ["LLM_PLANNER"] = "1"
    _reset_caches()

    plan = make_plan("现在坐地铁去纽约要多久")
    assert plan is not None
    assert plan.actions[0].args["transport_mode"] == "transit"


def test_eta_query_requested_walking_degrades_output_to_driving_eta(monkeypatch) -> None:
    _reset_caches()
    client = TestClient(app)
    monkeypatch.setattr(
        "personal_ops_agent.graph.nodes.planner.make_plan",
        lambda _message: ExecutionPlan(
            goal="estimate walking time to new york",
            intent="eta_query",
            actions=[
                {
                    "tool": "commute_plan",
                    "args": {
                        "destination": "New York",
                        "departure_time": "now",
                        "transport_mode": "walking",
                    },
                }
            ],
            reason="need walking eta",
            confidence=0.95,
        ),
    )
    response = client.post("/chat", json={"message": "我走路去纽约多久"})
    assert response.status_code == 200
    payload = response.json()
    recommendation = payload["state"]["commute"]["recommendation"]
    assert recommendation["transport_mode"] == "driving"
    assert "当前 ETA connector 仅支持 driving-first 估算" in recommendation["weather_advice"]
    assert "开车到New York" in payload["output"]


def test_chat_uses_todo_read_path(monkeypatch) -> None:
    _reset_caches()
    client = TestClient(app)
    monkeypatch.setattr(
        "personal_ops_agent.graph.nodes.planner.make_plan",
        lambda _message: ExecutionPlan(
            goal="list current todos",
            intent="todo_list",
            actions=[{"tool": "todo_read", "args": {}}],
            reason="need to read current todo tasks",
            confidence=0.92,
        ),
    )
    monkeypatch.setattr(
        "personal_ops_agent.graph.nodes.todo_read.list_todoist_tasks",
        lambda **_kwargs: [],
    )
    response = client.post("/chat", json={"message": "我有哪些todo"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "todo_list"
    assert payload["state"]["plan_used"] is True
    assert payload["state"]["eval"]["planner"]["executed_actions"] == ["todo_read"]
    assert "todo" in payload["state"]
