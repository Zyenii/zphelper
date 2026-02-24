import os

import pytest

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.router.intent import Intent
from personal_ops_agent.router.llm_router import llm_route, parse_llm_router_output


def _reset_settings() -> None:
    get_settings.cache_clear()


def test_parse_bad_json_raises() -> None:
    with pytest.raises(Exception):
        parse_llm_router_output("not-json")


def test_parse_invalid_intent_raises() -> None:
    with pytest.raises(Exception):
        parse_llm_router_output('{"intent":"not_allowed","confidence":0.9,"reason":"x"}')


def test_llm_route_confidence_gate(monkeypatch) -> None:
    os.environ["APP_ENV"] = "test"
    os.environ["LOG_LEVEL"] = "INFO"
    os.environ["OPENAI_API_KEY"] = "test-key"
    os.environ["LLM_ROUTER"] = "1"
    os.environ["LLM_ROUTER_THRESHOLD"] = "0.7"
    _reset_settings()

    monkeypatch.setattr(
        "personal_ops_agent.router.llm_router._call_openai_classifier",
        lambda _message, _model, _key: '{"intent":"schedule_summary","confidence":0.55,"reason":"low confidence"}',
    )
    result = llm_route("some message")
    assert result.intent == Intent.UNKNOWN.value
    assert result.reason == "low_confidence"


def test_llm_route_invalid_schema_returns_unknown(monkeypatch) -> None:
    os.environ["APP_ENV"] = "test"
    os.environ["LOG_LEVEL"] = "INFO"
    os.environ["OPENAI_API_KEY"] = "test-key"
    os.environ["LLM_ROUTER"] = "1"
    _reset_settings()

    monkeypatch.setattr(
        "personal_ops_agent.router.llm_router._call_openai_classifier",
        lambda _message, _model, _key: '{"intent":"hack","confidence":0.99,"reason":"oops"}',
    )
    result = llm_route("message")
    assert result.intent == Intent.UNKNOWN.value
    assert result.reason == "llm_error"
