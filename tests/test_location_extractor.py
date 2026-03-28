from __future__ import annotations

import os

from personal_ops_agent.commute.location_extractor import extract_locations_llm
from personal_ops_agent.core.settings import get_settings


def _reset_settings() -> None:
    get_settings.cache_clear()


def test_location_extractor_low_confidence_returns_none(monkeypatch) -> None:
    os.environ["APP_ENV"] = "test"
    os.environ["LOG_LEVEL"] = "INFO"
    os.environ["OPENAI_API_KEY"] = "test-key"
    os.environ["LLM_LOCATION_EXTRACTOR"] = "1"
    os.environ["LLM_LOCATION_EXTRACTOR_THRESHOLD"] = "0.8"
    _reset_settings()

    monkeypatch.setattr(
        "personal_ops_agent.commute.location_extractor._call_openai_location_extractor",
        lambda *_args, **_kwargs: (
            '{"origin":null,"destination":"chengdu famous food","confidence":0.4,"reason":"low confidence"}'
        ),
    )
    assert extract_locations_llm("我现在去chengdu famous food要多久") is None


def test_location_extractor_valid_result(monkeypatch) -> None:
    os.environ["APP_ENV"] = "test"
    os.environ["LOG_LEVEL"] = "INFO"
    os.environ["OPENAI_API_KEY"] = "test-key"
    os.environ["LLM_LOCATION_EXTRACTOR"] = "1"
    os.environ["LLM_LOCATION_EXTRACTOR_THRESHOLD"] = "0.7"
    _reset_settings()

    monkeypatch.setattr(
        "personal_ops_agent.commute.location_extractor._call_openai_location_extractor",
        lambda *_args, **_kwargs: (
            '{"origin":null,"destination":"chengdu famous food","confidence":0.92,"reason":"explicit destination"}'
        ),
    )
    result = extract_locations_llm("我现在去chengdu famous food要多久")
    assert result is not None
    assert result.destination == "chengdu famous food"
