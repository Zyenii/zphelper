import os
from datetime import datetime

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.graph.nodes.schedule_read import schedule_read_node
from personal_ops_agent.timewindow.llm import parse_time_window_llm


def _set_base_env() -> None:
    os.environ["APP_ENV"] = "test"
    os.environ["LOG_LEVEL"] = "INFO"
    os.environ["LLM_TIMEWINDOW"] = "1"
    os.environ["LLM_TIMEWINDOW_MODEL"] = "gpt-5-mini"
    os.environ["LLM_TIMEWINDOW_THRESHOLD"] = "0.75"
    os.environ["OPENAI_API_KEY"] = "test-key"


def test_timewindow_llm_invalid_json_returns_none(monkeypatch) -> None:
    _set_base_env()
    get_settings.cache_clear()
    now_local = datetime.fromisoformat("2026-02-18T09:30:00-05:00")
    monkeypatch.setattr(
        "personal_ops_agent.timewindow.llm._call_openai_timewindow",
        lambda *_args, **_kwargs: "NOT_JSON",
    )
    result = parse_time_window_llm("下周三下午我忙吗", now_local, "America/New_York")
    assert result is None


def test_timewindow_llm_low_confidence_returns_none(monkeypatch) -> None:
    _set_base_env()
    get_settings.cache_clear()
    now_local = datetime.fromisoformat("2026-02-18T09:30:00-05:00")
    monkeypatch.setattr(
        "personal_ops_agent.timewindow.llm._call_openai_timewindow",
        lambda *_args, **_kwargs: (
            '{"start_local":"2026-02-25T12:00:00","end_local":"2026-02-25T18:00:00",'
            '"timezone":"America/New_York","confidence":0.4,"reason":"uncertain"}'
        ),
    )
    result = parse_time_window_llm("下周三下午我忙吗", now_local, "America/New_York")
    assert result is None


def test_timewindow_llm_not_called_for_non_schedule_intent(monkeypatch) -> None:
    os.environ["APP_ENV"] = "test"
    os.environ["LOG_LEVEL"] = "INFO"
    os.environ["LLM_TIMEWINDOW"] = "1"
    os.environ["OPENAI_API_KEY"] = "test-key"
    os.environ["DEFAULT_TIMEZONE"] = "America/New_York"
    os.environ["TIMEWINDOW_NOW_ISO"] = "2026-02-18T09:30:00-05:00"
    os.environ["MOCK_CALENDAR"] = "1"
    os.environ["GOOGLE_CALENDAR_MODE"] = "mock"
    os.environ["CALENDAR_FIXTURE_PATH"] = "tests/fixtures/sample_calendar.json"
    get_settings.cache_clear()

    called = {"llm": False}

    def _raise_if_called(*_args, **_kwargs):
        called["llm"] = True
        raise AssertionError("LLM time-window parser should not be called for non-schedule intents")

    monkeypatch.setattr("personal_ops_agent.graph.nodes.schedule_read.parse_time_window_llm", _raise_if_called)
    result = schedule_read_node({"intent": "commute_advice", "user_message": "我几点出发去下一个日程"})
    assert called["llm"] is False
    assert "calendar" in result
