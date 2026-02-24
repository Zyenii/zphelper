import os

import pytest

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.router.llm_router import _call_openai_classifier, parse_llm_router_output


def test_live_llm_router_connectivity() -> None:
    # Avoid stale shell overrides; prefer .env values via get_settings().
    for key in ("OPENAI_API_KEY", "LLM_ROUTER", "LLM_ROUTER_MODEL", "LLM_ROUTER_THRESHOLD"):
        os.environ.pop(key, None)

    get_settings.cache_clear()
    settings = get_settings()
    if os.getenv("RUN_LLM_LIVE_TEST") != "1":
        pytest.skip("Set RUN_LLM_LIVE_TEST=1 to run live connectivity test.")
    if not settings.LLM_ROUTER:
        pytest.skip("Set LLM_ROUTER=1 in .env to run live connectivity test.")
    if not settings.OPENAI_API_KEY:
        pytest.skip("Set OPENAI_API_KEY in .env to run live connectivity test.")

    raw = _call_openai_classifier(
        "请判断这个请求是日程查询：我今天有什么安排？",
        settings.LLM_ROUTER_MODEL,
        settings.OPENAI_API_KEY,
    )
    parsed = parse_llm_router_output(raw)
    if os.getenv("SHOW_LLM_TEST_OUTPUT") == "1":
        print("\n[LLM RAW]", raw)
        print("[LLM PARSED]", parsed)
    assert parsed.intent in {"schedule_summary", "unknown", "commute_advice", "weather_summary", "eta_query"}
    assert 0.0 <= parsed.confidence <= 1.0
    assert isinstance(parsed.reason, str) and parsed.reason
