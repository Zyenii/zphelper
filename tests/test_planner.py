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
    os.environ["SESSION_CONTEXT_STORE_PATH"] = "tests/fixtures/test_session_context.json"
    _reset_caches()
    client = TestClient(app)
    monkeypatch.setattr(
        "personal_ops_agent.graph.nodes.planner.make_plan",
        lambda _message, **_kwargs: ExecutionPlan(
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
    os.environ["SESSION_CONTEXT_STORE_PATH"] = "tests/fixtures/test_session_context.json"
    _reset_caches()
    client = TestClient(app)
    monkeypatch.setattr(
        "personal_ops_agent.graph.nodes.planner.make_plan",
        lambda _message, **_kwargs: ExecutionPlan(
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
    os.environ["SESSION_CONTEXT_STORE_PATH"] = "tests/fixtures/test_session_context.json"
    _reset_caches()
    client = TestClient(app)
    monkeypatch.setattr(
        "personal_ops_agent.graph.nodes.planner.make_plan",
        lambda _message, **_kwargs: ExecutionPlan(
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
    os.environ["SESSION_CONTEXT_STORE_PATH"] = "tests/fixtures/test_session_context.json"
    _reset_caches()
    client = TestClient(app)
    monkeypatch.setattr(
        "personal_ops_agent.graph.nodes.planner.make_plan",
        lambda _message, **_kwargs: ExecutionPlan(
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
    os.environ["SESSION_CONTEXT_STORE_PATH"] = "tests/fixtures/test_session_context.json"
    _reset_caches()
    client = TestClient(app)
    monkeypatch.setattr(
        "personal_ops_agent.graph.nodes.planner.make_plan",
        lambda _message, **_kwargs: ExecutionPlan(
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


def test_clarification_flow_persists_continuation_until_answer_is_complete(monkeypatch, tmp_path) -> None:
    session_store = tmp_path / "session_context.json"
    os.environ["SESSION_CONTEXT_STORE_PATH"] = str(session_store)
    os.environ["MAX_CLARIFICATION_TURNS"] = "3"
    _reset_caches()
    client = TestClient(app)

    def fake_make_plan(message: str, **_kwargs) -> ExecutionPlan:
        if message == "我现在过去要多久":
            return ExecutionPlan(
                status="needs_clarification",
                goal="estimate eta",
                intent="eta_query",
                actions=[],
                reason="destination missing",
                confidence=0.95,
                missing_slots=["destination"],
                clarification_question="你想去哪里？",
            )
        return ExecutionPlan(
            status="ready",
            goal="estimate eta",
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
            reason="destination resolved",
            confidence=0.95,
            known_slots={"destination": "New York"},
        )

    monkeypatch.setattr("personal_ops_agent.graph.nodes.planner.make_plan", fake_make_plan)

    first = client.post("/chat", json={"message": "我现在过去要多久", "session_id": "s1"})
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["output"] == "你想去哪里？"
    assert session_store.exists()
    assert "你想去哪里？" in session_store.read_text(encoding="utf-8")

    second = client.post("/chat", json={"message": "纽约", "session_id": "s1"})
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["state"]["plan_used"] is True
    assert second_body["state"]["commute"]["recommendation"]["destination"] == "New York"
    if session_store.exists():
        assert "s1" not in session_store.read_text(encoding="utf-8")


def test_clarification_stops_after_max_turns(monkeypatch, tmp_path) -> None:
    session_store = tmp_path / "session_context.json"
    os.environ["SESSION_CONTEXT_STORE_PATH"] = str(session_store)
    os.environ["MAX_CLARIFICATION_TURNS"] = "3"
    _reset_caches()
    client = TestClient(app)

    monkeypatch.setattr(
        "personal_ops_agent.graph.nodes.planner.make_plan",
        lambda _message, **_kwargs: ExecutionPlan(
            status="needs_clarification",
            goal="estimate eta",
            intent="eta_query",
            actions=[],
            reason="destination missing",
            confidence=0.95,
            missing_slots=["destination"],
            clarification_question="你想去哪里？",
        ),
    )

    first = client.post("/chat", json={"message": "我现在过去要多久", "session_id": "s2"})
    second = client.post("/chat", json={"message": "嗯", "session_id": "s2"})
    third = client.post("/chat", json={"message": "不知道", "session_id": "s2"})

    assert first.json()["output"] == "你想去哪里？"
    assert second.json()["output"] == "你想去哪里？"
    assert third.json()["output"] == "当前信息仍不足以完成这个任务，请重新完整描述你的需求。"
    if session_store.exists():
        assert "s2" not in session_store.read_text(encoding="utf-8")
