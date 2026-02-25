from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.eval.metrics import record_write
from personal_ops_agent.eval.postgres_logger import log_run_event
from personal_ops_agent.todo.schemas import TodoCreateResult, TodoDraft, TodoTaskSummary

logger = logging.getLogger(__name__)


class TodoistError(RuntimeError):
    pass


def list_todoist_tasks(*, trace_id: str | None, limit: int = 5) -> list[TodoTaskSummary]:
    settings = get_settings()
    if not settings.TODOIST_API_TOKEN:
        return []
    req = Request(
        f"https://api.todoist.com/api/v1/tasks?limit={max(1, min(limit, 20))}",
        headers={"Authorization": f"Bearer {settings.TODOIST_API_TOKEN}"},
        method="GET",
    )
    try:
        with urlopen(req, timeout=12) as response:  # noqa: S310
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:  # noqa: BLE001
            detail = ""
        raise TodoistError(f"Todoist list HTTP {exc.code}: {detail or exc.reason}") from exc
    except URLError as exc:
        raise TodoistError(f"Todoist list network error: {exc}") from exc

    tasks: list[TodoTaskSummary] = []
    raw_items = data.get("results", []) if isinstance(data, dict) else data
    if isinstance(raw_items, list):
        for item in raw_items[:limit]:
            due_obj = item.get("due") or {}
            due_value = due_obj.get("datetime") or due_obj.get("date")
            task_id = str(item.get("id", ""))
            tasks.append(
                TodoTaskSummary(
                    task_id=task_id,
                    title=str(item.get("content", "")),
                    due=due_value,
                    priority=int(item.get("priority", 2)),
                    url=item.get("url") or (f"https://app.todoist.com/app/task/{task_id}" if task_id else None),
                )
            )
    logger.info("todo.list_loaded count=%s", len(tasks))
    return tasks


def _build_todoist_payload(todo: TodoDraft) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "content": todo.title,
        "priority": todo.priority,
        "labels": todo.labels,
    }
    if todo.project_id:
        payload["project_id"] = todo.project_id
    if todo.notes:
        payload["description"] = todo.notes
    if todo.due:
        if "T" in todo.due:
            due_dt = datetime.fromisoformat(todo.due.replace("Z", "+00:00"))
            payload["due_datetime"] = due_dt.isoformat()
        else:
            payload["due_date"] = todo.due
    return payload


def create_todoist_task(todo: TodoDraft, *, trace_id: str | None) -> TodoCreateResult:
    settings = get_settings()
    if not settings.TODOIST_API_TOKEN:
        raise TodoistError("TODOIST_API_TOKEN is not configured.")
    start = time.perf_counter()
    payload = _build_todoist_payload(todo)
    req = Request(
        "https://api.todoist.com/api/v1/tasks",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.TODOIST_API_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=15) as response:  # noqa: S310
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:  # noqa: BLE001
            detail = ""
        record_write(False)
        log_run_event(
            flow="todo_write",
            trace_id=trace_id,
            prompt_version=settings.PROMPT_VERSION,
            tokens=None,
            latency_ms=int((time.perf_counter() - start) * 1000),
            tool_success=False,
            validation_errors=detail or str(exc),
            confidence=todo.confidence,
            extra={"status_code": exc.code},
        )
        raise TodoistError(f"Todoist HTTP {exc.code}: {detail or exc.reason}") from exc
    except URLError as exc:
        record_write(False)
        log_run_event(
            flow="todo_write",
            trace_id=trace_id,
            prompt_version=settings.PROMPT_VERSION,
            tokens=None,
            latency_ms=int((time.perf_counter() - start) * 1000),
            tool_success=False,
            validation_errors=str(exc),
            confidence=todo.confidence,
            extra={},
        )
        raise TodoistError(f"Todoist network error: {exc}") from exc

    task_id = str(data.get("id", ""))
    result = TodoCreateResult(
        task_id=task_id,
        url=data.get("url") or (f"https://app.todoist.com/app/task/{task_id}" if task_id else None),
        normalized_due=(data.get("due") or {}).get("datetime") or (data.get("due") or {}).get("date"),
        priority=int(data.get("priority", todo.priority)),
    )
    record_write(True)
    log_run_event(
        flow="todo_write",
        trace_id=trace_id,
        prompt_version=settings.PROMPT_VERSION,
        tokens=None,
        latency_ms=int((time.perf_counter() - start) * 1000),
        tool_success=True,
        validation_errors=None,
        confidence=todo.confidence,
        extra={"task_id": result.task_id},
    )
    return result
