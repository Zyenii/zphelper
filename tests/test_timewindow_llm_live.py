from datetime import datetime
import os

import pytest

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.timewindow.llm import parse_time_window_llm


def test_timewindow_llm_live_examples() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    if not (os.getenv("RUN_LLM_LIVE_TEST") == "1" and settings.LLM_TIMEWINDOW and settings.OPENAI_API_KEY):
        pytest.skip("Requires RUN_LLM_LIVE_TEST=1, LLM_TIMEWINDOW=1 and OPENAI_API_KEY.")

    now_local = datetime.fromisoformat("2026-02-18T09:30:00-05:00")
    messages = [
        "下周三下午我忙吗",
        "Can you show my schedule for the next 3 days?",
        "这周末有什么安排",
    ]
    for message in messages:
        window = parse_time_window_llm(message, now_local, settings.DEFAULT_TIMEZONE)
        assert window is not None
        assert window.end_utc > window.start_utc
