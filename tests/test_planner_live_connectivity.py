import os

import pytest

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.planner.planner import _call_openai_planner
from personal_ops_agent.planner.schemas import ExecutionPlan


def test_live_planner_connectivity() -> None:
    # Avoid stale shell overrides; prefer .env values via get_settings().
    for key in ("OPENAI_API_KEY", "LLM_PLANNER", "LLM_PLANNER_MODEL", "LLM_PLANNER_THRESHOLD"):
        os.environ.pop(key, None)

    get_settings.cache_clear()
    settings = get_settings()
    if os.getenv("RUN_LLM_LIVE_TEST") != "1":
        pytest.skip("Set RUN_LLM_LIVE_TEST=1 to run live planner connectivity test.")
    if not settings.LLM_PLANNER:
        pytest.skip("Set LLM_PLANNER=1 in .env to run live planner connectivity test.")
    if not settings.OPENAI_API_KEY:
        pytest.skip("Set OPENAI_API_KEY in .env to run live planner connectivity test.")

    raw = _call_openai_planner(
        "我现在去纽约要多久",
        settings.LLM_PLANNER_MODEL,
        settings.OPENAI_API_KEY,
        settings.LLM_PLANNER_MAX_ACTIONS,
    )
    parsed = ExecutionPlan.model_validate_json(raw)
    if os.getenv("SHOW_LLM_TEST_OUTPUT") == "1":
        print("\n[PLANNER RAW]", raw)
        print("[PLANNER PARSED]", parsed)
    assert parsed.intent in {
        "schedule_summary",
        "unknown",
        "commute_advice",
        "weather_summary",
        "eta_query",
        "todo_list",
        "todo_create",
        "leaving_checklist",
        "calendar_create",
    }
    assert 0.0 <= parsed.confidence <= 1.0
    assert isinstance(parsed.reason, str) and parsed.reason
    assert isinstance(parsed.goal, str) and parsed.goal
