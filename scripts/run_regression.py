from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.graph.build import build_graph
from personal_ops_agent.main import app


def _set_mock_env() -> None:
    os.environ["APP_ENV"] = "test"
    os.environ["LOG_LEVEL"] = "INFO"
    os.environ["PREFER_DOTENV_IN_DEV"] = "0"
    os.environ["MOCK_CALENDAR"] = "1"
    os.environ["GOOGLE_CALENDAR_MODE"] = "mock"
    os.environ["CALENDAR_FIXTURE_PATH"] = "tests/fixtures/sample_calendar.json"
    os.environ["MOCK_WEATHER"] = "1"
    os.environ["WEATHER_MODE"] = "mock"
    os.environ["WEATHER_FIXTURE_PATH"] = "tests/fixtures/sample_weather.json"
    os.environ["MOCK_ETA"] = "1"
    os.environ["ETA_PROVIDER"] = "mock"
    os.environ["ETA_MODE"] = "mock"
    os.environ["ETA_FIXTURE_PATH"] = "tests/fixtures/sample_eta.json"
    os.environ["OPENAI_API_KEY"] = ""
    os.environ["LLM_ROUTER"] = "0"
    os.environ["UNKNOWN_LLM_REPLY"] = "0"


def _read_path(payload: dict[str, Any], path: str) -> Any:
    node: Any = payload
    for part in path.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node


def run_golden() -> tuple[int, int]:
    _set_mock_env()
    get_settings.cache_clear()
    build_graph.cache_clear()

    fixture = json.loads(Path("tests/fixtures/golden_m7_v1.json").read_text(encoding="utf-8"))
    client = TestClient(app)
    passed = 0
    total = len(fixture)
    print("=== Golden Eval M7 v1 ===")
    for idx, case in enumerate(fixture, start=1):
        resp = client.post("/chat", json={"message": case["message"]})
        ok = resp.status_code == 200
        body = resp.json() if ok else {}
        intent_ok = body.get("intent") == case["expected_intent"]
        paths_ok = all(_read_path(body, path) is not None for path in case.get("required_paths", []))
        case_ok = ok and intent_ok and paths_ok
        if case_ok:
            passed += 1
        print(
            f"[{idx:02d}] {'PASS' if case_ok else 'FAIL'} "
            f"intent={body.get('intent')} expected={case['expected_intent']}"
        )
    print(f"Golden pass rate: {passed}/{total} ({(passed / total) * 100:.1f}%)")
    return passed, total


def run_pytests() -> int:
    print("=== Pytest Core ===")
    cmd = [sys.executable, "-m", "pytest", "-q"]
    completed = subprocess.run(cmd, check=False)
    return completed.returncode


def main() -> int:
    pytest_code = run_pytests()
    golden_passed, golden_total = run_golden()
    overall_ok = pytest_code == 0 and golden_passed == golden_total
    print("=== Regression Summary ===")
    print(f"pytest_ok={pytest_code == 0}")
    print(f"golden_ok={golden_passed == golden_total}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
