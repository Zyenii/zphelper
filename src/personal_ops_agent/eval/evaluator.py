from __future__ import annotations

import json
import os
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from fastapi.testclient import TestClient

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.graph.build import build_graph
from personal_ops_agent.main import app


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_path(payload: dict[str, Any], path: str) -> Any:
    node: Any = payload
    for part in path.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node


def _default_mock_env() -> dict[str, str]:
    return {
        "APP_ENV": "test",
        "LOG_LEVEL": "INFO",
        "PREFER_DOTENV_IN_DEV": "0",
        "MOCK_CALENDAR": "1",
        "GOOGLE_CALENDAR_MODE": "mock",
        "CALENDAR_FIXTURE_PATH": "tests/fixtures/sample_calendar.json",
        "MOCK_WEATHER": "1",
        "WEATHER_MODE": "mock",
        "WEATHER_FIXTURE_PATH": "tests/fixtures/sample_weather.json",
        "MOCK_ETA": "1",
        "ETA_PROVIDER": "mock",
        "ETA_MODE": "mock",
        "ETA_FIXTURE_PATH": "tests/fixtures/sample_eta.json",
        "UNKNOWN_LLM_REPLY": "0",
    }


def _apply_env(overrides: dict[str, str]) -> None:
    for key, value in {**_default_mock_env(), **overrides}.items():
        os.environ[key] = value
    get_settings.cache_clear()
    build_graph.cache_clear()


@dataclass
class EvalCase:
    id: str
    message: str
    expected_intent: str
    expected_tools: list[str]
    required_paths: list[str]
    checks_output_matches_state: bool = False


@dataclass
class CaseResult:
    id: str
    message: str
    intent_ok: bool
    tool_chain_ok: bool
    execution_ok: bool
    output_consistency_ok: bool
    required_paths_ok: bool
    total_ok: bool
    planner_used: bool
    intent: str
    planned_actions: list[str]
    executed_actions: list[str]
    llm_calls: int
    total_tokens: int
    request_latency_ms: int
    estimated_cost_usd: float
    failure_reasons: list[str]


@dataclass
class SuiteSummary:
    variant: str
    total_cases: int
    passed_cases: int
    intent_accuracy: float
    tool_chain_accuracy: float
    execution_fidelity: float
    output_consistency: float
    required_path_coverage: float
    avg_llm_calls: float
    avg_total_tokens: float
    avg_request_latency_ms: float
    avg_estimated_cost_usd: float


@dataclass
class EvalReport:
    summary: SuiteSummary
    cases: list[CaseResult]


def load_eval_cases(path: str = "tests/fixtures/agent_eval_v1.json") -> list[EvalCase]:
    fixture_path = Path(path)
    if not fixture_path.is_absolute():
        fixture_path = _repo_root() / fixture_path
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    return [EvalCase(**item) for item in payload]


def _bool_ratio(values: list[bool]) -> float:
    return sum(1 for value in values if value) / len(values) if values else 0.0


def _deterministic_chain_for_intent(intent: str) -> list[str]:
    mapping = {
        "schedule_summary": ["schedule_read", "schedule_summarize"],
        "weather_summary": ["weather_read", "weather_summarize"],
        "eta_query": ["commute_plan"],
        "commute_advice": ["schedule_read", "weather_read", "commute_plan"],
        "todo_create": ["schedule_read", "todo_parse", "todo_write"],
        "todo_list": ["todo_read"],
        "leaving_checklist": ["schedule_read", "weather_read", "commute_plan", "checklist_generate"],
        "calendar_create": ["calendar_create"],
    }
    return mapping.get(intent, [])


def _exception_case_result(case: EvalCase, exc: Exception, *, require_planner_trace: bool) -> CaseResult:
    failure_reasons = [f"case execution error: {type(exc).__name__}: {exc}"]
    if require_planner_trace:
        failure_reasons.append("planner not used")
    return CaseResult(
        id=case.id,
        message=case.message,
        intent_ok=False,
        tool_chain_ok=False,
        execution_ok=False,
        output_consistency_ok=False,
        required_paths_ok=False,
        total_ok=False,
        planner_used=False,
        intent="error",
        planned_actions=[],
        executed_actions=[],
        llm_calls=0,
        total_tokens=0,
        request_latency_ms=0,
        estimated_cost_usd=0.0,
        failure_reasons=failure_reasons,
    )


def _evaluate_case(client: TestClient, case: EvalCase, *, require_planner_trace: bool) -> CaseResult:
    try:
        response = client.post("/chat", json={"message": case.message})
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return _exception_case_result(case, exc, require_planner_trace=require_planner_trace)
    payload = response.json() if response.status_code == 200 else {}

    intent = str(payload.get("intent", "unknown"))
    state = payload.get("state", {}) if isinstance(payload.get("state"), dict) else {}
    planner_used = bool(state.get("plan_used", False))
    eval_state = state.get("eval", {}) if isinstance(state.get("eval"), dict) else {}
    planner_eval = eval_state.get("planner", {}) if isinstance(eval_state.get("planner"), dict) else {}
    runtime = eval_state.get("runtime", {}) if isinstance(eval_state.get("runtime"), dict) else {}

    planned_actions = planner_eval.get("planned_actions", [])
    executed_actions = planner_eval.get("executed_actions", [])
    if not isinstance(planned_actions, list):
        planned_actions = []
    if not isinstance(executed_actions, list):
        executed_actions = []

    if not require_planner_trace and not planned_actions and not executed_actions:
        inferred_chain = _deterministic_chain_for_intent(intent)
        planned_actions = inferred_chain
        executed_actions = inferred_chain

    intent_ok = intent == case.expected_intent
    tool_chain_ok = planned_actions == case.expected_tools if case.expected_tools else intent_ok
    execution_ok = executed_actions == planned_actions
    required_paths_ok = all(_read_path(payload, path) is not None for path in case.required_paths)

    output_consistency_ok = True
    if case.checks_output_matches_state:
        output_value = payload.get("output")
        state_output = _read_path(payload, "state.output")
        output_consistency_ok = output_value == state_output

    failure_reasons: list[str] = []
    if not intent_ok:
        failure_reasons.append(f"intent mismatch: expected={case.expected_intent} actual={intent}")
    if require_planner_trace and not planner_used:
        failure_reasons.append("planner not used")
    if not tool_chain_ok:
        failure_reasons.append(f"tool chain mismatch: expected={case.expected_tools} actual={planned_actions}")
    if not execution_ok:
        failure_reasons.append(f"execution mismatch: planned={planned_actions} executed={executed_actions}")
    if not required_paths_ok:
        failure_reasons.append(f"missing required paths: {case.required_paths}")
    if not output_consistency_ok:
        failure_reasons.append("output inconsistent with state.output")

    total_ok = not failure_reasons

    return CaseResult(
        id=case.id,
        message=case.message,
        intent_ok=intent_ok,
        tool_chain_ok=tool_chain_ok,
        execution_ok=execution_ok,
        output_consistency_ok=output_consistency_ok,
        required_paths_ok=required_paths_ok,
        total_ok=total_ok,
        planner_used=planner_used,
        intent=intent,
        planned_actions=[str(item) for item in planned_actions],
        executed_actions=[str(item) for item in executed_actions],
        llm_calls=int(runtime.get("llm_calls", 0) or 0),
        total_tokens=int(runtime.get("total_tokens", 0) or 0),
        request_latency_ms=int(runtime.get("request_latency_ms", 0) or 0),
        estimated_cost_usd=float(runtime.get("estimated_cost_usd", 0.0) or 0.0),
        failure_reasons=failure_reasons,
    )


def evaluate_suite(
    *,
    variant: str,
    env_overrides: dict[str, str],
    fixture_path: str = "tests/fixtures/agent_eval_v1.json",
    require_planner_trace: bool = False,
) -> EvalReport:
    _apply_env(env_overrides)
    client = TestClient(app)
    cases = load_eval_cases(fixture_path)
    results = [_evaluate_case(client, case, require_planner_trace=require_planner_trace) for case in cases]

    summary = SuiteSummary(
        variant=variant,
        total_cases=len(results),
        passed_cases=sum(1 for item in results if item.total_ok),
        intent_accuracy=_bool_ratio([item.intent_ok for item in results]),
        tool_chain_accuracy=_bool_ratio([item.tool_chain_ok for item in results]),
        execution_fidelity=_bool_ratio([item.execution_ok for item in results]),
        output_consistency=_bool_ratio([item.output_consistency_ok for item in results]),
        required_path_coverage=_bool_ratio([item.required_paths_ok for item in results]),
        avg_llm_calls=mean([item.llm_calls for item in results]) if results else 0.0,
        avg_total_tokens=mean([item.total_tokens for item in results]) if results else 0.0,
        avg_request_latency_ms=mean([item.request_latency_ms for item in results]) if results else 0.0,
        avg_estimated_cost_usd=mean([item.estimated_cost_usd for item in results]) if results else 0.0,
    )
    return EvalReport(summary=summary, cases=results)


def report_to_dict(report: EvalReport) -> dict[str, Any]:
    return {
        "summary": asdict(report.summary),
        "cases": [asdict(case) for case in report.cases],
    }


def planner_variant_enabled() -> bool:
    settings = get_settings()
    return bool(settings.OPENAI_API_KEY)
