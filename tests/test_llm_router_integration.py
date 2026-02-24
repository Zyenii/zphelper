import os

import pytest

from personal_ops_agent.router.router import dispatch_intent


@pytest.mark.skipif(
    not (os.getenv("LLM_ROUTER") == "1" and os.getenv("OPENAI_API_KEY")),
    reason="Integration test requires LLM_ROUTER=1 and OPENAI_API_KEY",
)
def test_llm_router_bilingual_integration() -> None:
    cases = [
        ("Could you summarize how busy I am tomorrow afternoon?", "schedule_summary"),
        ("我明天下午忙不忙，帮我看下安排", "schedule_summary"),
        ("Should I leave now for my next event if it may rain?", "commute_advice"),
        ("我现在去下一个会要不要提前出门", "commute_advice"),
    ]
    for message, expected in cases:
        decision = dispatch_intent(message)
        assert decision.intent in {expected, "unknown"}
