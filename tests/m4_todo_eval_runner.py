from __future__ import annotations

import json
import os
from pathlib import Path

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.todo.parser import parse_todo_with_retries
from personal_ops_agent.todo.schemas import TodoDraft


def run() -> int:
    os.environ["OPENAI_API_KEY"] = ""
    get_settings.cache_clear()
    fixture_path = Path("tests/fixtures/todo_m4_cases.json")
    cases = json.loads(fixture_path.read_text(encoding="utf-8"))
    settings = get_settings()
    total = len(cases)
    schema_valid = 0
    write_gate_ok = 0

    for idx, case in enumerate(cases, start=1):
        draft = parse_todo_with_retries(case["input"], trace_id=f"todo-eval-{idx}", context={})
        try:
            TodoDraft.model_validate(draft.model_dump())
            schema_valid += 1
            schema_ok = True
        except Exception:
            schema_ok = False
        should_write = draft.confidence >= settings.TODO_CONFIDENCE_THRESHOLD
        expected_write = bool(case.get("expected", {}).get("should_write", False))
        gate_ok = should_write == expected_write
        if gate_ok:
            write_gate_ok += 1

        print(
            f"[{idx:02d}] schema={'PASS' if schema_ok else 'FAIL'} "
            f"write_gate={'PASS' if gate_ok else 'FAIL'} "
            f"title={draft.title!r} confidence={draft.confidence:.2f}"
        )

    print(f"schema_valid: {schema_valid}/{total}")
    print(f"write_gate_match: {write_gate_ok}/{total}")
    return 0 if schema_valid == total and write_gate_ok == total else 1


if __name__ == "__main__":
    raise SystemExit(run())
