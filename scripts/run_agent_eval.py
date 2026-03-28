from __future__ import annotations

import json
import os
from pathlib import Path

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.eval.evaluator import evaluate_suite, report_to_dict


def _print_summary(summary: dict) -> None:
    print(f"variant={summary['variant']}")
    print(f"passed={summary['passed_cases']}/{summary['total_cases']}")
    print(f"intent_accuracy={summary['intent_accuracy']:.2%}")
    print(f"tool_chain_accuracy={summary['tool_chain_accuracy']:.2%}")
    print(f"execution_fidelity={summary['execution_fidelity']:.2%}")
    print(f"output_consistency={summary['output_consistency']:.2%}")
    print(f"required_path_coverage={summary['required_path_coverage']:.2%}")
    print(f"avg_llm_calls={summary['avg_llm_calls']:.2f}")
    print(f"avg_total_tokens={summary['avg_total_tokens']:.2f}")
    print(f"avg_request_latency_ms={summary['avg_request_latency_ms']:.2f}")
    print(f"avg_estimated_cost_usd={summary['avg_estimated_cost_usd']:.6f}")


def _print_failures(report: dict) -> None:
    failed = [case for case in report["cases"] if not case["total_ok"]]
    if not failed:
        print("failed_cases=0")
        return
    print(f"failed_cases={len(failed)}")
    for case in failed:
        print(f"- id={case['id']}")
        print(f"  message={case['message']}")
        print(f"  intent={case['intent']}")
        print(f"  planner_used={case['planner_used']}")
        print(f"  planned_actions={case['planned_actions']}")
        print(f"  executed_actions={case['executed_actions']}")
        print(f"  llm_calls={case['llm_calls']}")
        print(f"  failure_reasons={case['failure_reasons']}")


def main() -> int:
    output_dir = Path("artifacts")
    output_dir.mkdir(exist_ok=True)
    settings = get_settings()
    original_openai_key = (settings.OPENAI_API_KEY or "").strip()
    planner_key_available = bool(original_openai_key)

    baseline = evaluate_suite(
        variant="workflow_baseline",
        env_overrides={
            "OPENAI_API_KEY": "",
            "LLM_ROUTER": "0",
            "LLM_PLANNER": "0",
            "LLM_TIMEWINDOW": "0",
            "LLM_LOCATION_EXTRACTOR": "0",
        },
    )
    baseline_dict = report_to_dict(baseline)
    (output_dir / "agent_eval_workflow_baseline.json").write_text(
        json.dumps(baseline_dict, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("=== Agent Eval: Workflow Baseline ===")
    _print_summary(baseline_dict["summary"])
    _print_failures(baseline_dict)

    if planner_key_available:
        planner = evaluate_suite(
            variant="planner_variant",
            env_overrides={
                "OPENAI_API_KEY": original_openai_key,
                "LLM_PLANNER": "1",
                "LLM_ROUTER": "0",
                "LLM_TIMEWINDOW": "0",
            },
            require_planner_trace=True,
        )
        planner_dict = report_to_dict(planner)
        (output_dir / "agent_eval_planner_variant.json").write_text(
            json.dumps(planner_dict, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("\n=== Agent Eval: Planner Variant ===")
        _print_summary(planner_dict["summary"])
        _print_failures(planner_dict)
    else:
        print("\n=== Agent Eval: Planner Variant Skipped ===")
        print("No OPENAI_API_KEY available; planner A/B variant not executed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
