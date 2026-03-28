from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "INFO")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("LLM_ROUTER", "0")
os.environ.setdefault("LLM_PLANNER", "0")
os.environ.setdefault("UNKNOWN_LLM_REPLY", "0")

from personal_ops_agent.main import app


def test_runtime_stats_present_in_chat_response() -> None:
    client = TestClient(app)
    resp = client.post("/chat", json={"message": "hello"})
    assert resp.status_code == 200
    payload = resp.json()
    runtime = payload["state"]["eval"]["runtime"]
    required = {
        "llm_calls",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "estimated_cost_usd",
        "retry_count",
        "llm_latency_ms",
        "request_latency_ms",
        "llm_error_count",
    }
    assert required.issubset(set(runtime.keys()))
    assert isinstance(runtime["llm_calls"], int)
    assert isinstance(runtime["retry_count"], int)
    assert isinstance(runtime["request_latency_ms"], int)


def test_m7_golden_fixture_has_ten_cases() -> None:
    cases = json.loads(Path("tests/fixtures/golden_m7_v1.json").read_text(encoding="utf-8"))
    assert len(cases) == 10
