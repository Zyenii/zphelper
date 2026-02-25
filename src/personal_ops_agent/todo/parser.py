from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.core.telemetry import record_llm_usage, record_retry
from personal_ops_agent.eval.metrics import record_parse
from personal_ops_agent.eval.postgres_logger import log_run_event
from personal_ops_agent.todo.schemas import TODO_JSON_SCHEMA, TodoDraft

logger = logging.getLogger(__name__)


def _extract_text_from_openai_response(payload: dict[str, Any]) -> str:
    output = payload.get("output", [])
    for item in output:
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return str(content.get("text", ""))
    text = payload.get("output_text")
    if isinstance(text, str):
        return text
    raise ValueError("No output text found in LLM response")


def _build_prompt(raw_text: str, context: dict[str, Any] | None, strict_error: str | None = None) -> str:
    context_json = json.dumps(context or {}, ensure_ascii=False)
    strict_hint = f"\nPrevious validation error: {strict_error}\nFix it exactly." if strict_error else ""
    return (
        "You convert user text into Todo JSON.\n"
        "Output strict JSON only, no markdown.\n"
        "Required keys: title, due, priority, labels, project_id, notes, source_event_id, confidence, rationale.\n"
        "If unknown optional fields, set null or empty list.\n"
        "confidence must be 0..1.\n"
        f"JSON Schema: {json.dumps(TODO_JSON_SCHEMA, ensure_ascii=False)}\n"
        f"Context: {context_json}\n"
        f"User: {raw_text}\n"
        f"{strict_hint}"
    )


def _call_openai_todo(prompt: str, model: str, api_key: str) -> tuple[str, int | None]:
    body = {
        "model": model,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
    }
    req = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=15) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    record_llm_usage(model=model, usage=payload.get("usage"))
    usage = payload.get("usage", {})
    tokens = usage.get("total_tokens") if isinstance(usage, dict) else None
    return _extract_text_from_openai_response(payload), tokens if isinstance(tokens, int) else None


def _rule_todo(raw_text: str, context: dict[str, Any] | None) -> TodoDraft:
    text = raw_text.strip()
    title = text
    prefix = re.compile(r"^(add|todo|task|remind me to|提醒我|帮我|请|创建待办)\s*", re.IGNORECASE)
    title = prefix.sub("", title).strip("：: ")
    due: str | None = None
    today = datetime.now(timezone.utc).date()
    if "tomorrow" in raw_text.lower() or "明天" in raw_text:
        due = str(today + timedelta(days=1))
    if "today" in raw_text.lower() or "今天" in raw_text:
        due = str(today)
    priority = 2
    if any(word in raw_text.lower() for word in ["urgent", "asap"]) or "紧急" in raw_text:
        priority = 4
    source_event_id = None
    if context and isinstance(context.get("next_event"), dict):
        source_event_id = context["next_event"].get("id")
    return TodoDraft(
        title=title or "Untitled task",
        due=due,
        priority=priority,
        labels=[],
        project_id=None,
        notes=None,
        source_event_id=source_event_id,
        confidence=0.55,
        rationale="rule_fallback",
    )


def parse_todo_with_retries(
    raw_text: str,
    *,
    trace_id: str | None,
    context: dict[str, Any] | None = None,
) -> TodoDraft:
    settings = get_settings()
    start = time.perf_counter()
    validation_error: str | None = None
    tokens: int | None = None
    if not settings.OPENAI_API_KEY:
        draft = _rule_todo(raw_text, context)
        record_parse(True)
        log_run_event(
            flow="todo_parse",
            trace_id=trace_id,
            prompt_version=settings.PROMPT_VERSION,
            tokens=0,
            latency_ms=int((time.perf_counter() - start) * 1000),
            tool_success=True,
            validation_errors=None,
            confidence=draft.confidence,
            extra={"mode": "rule_no_key"},
        )
        return draft

    retries = max(0, settings.TODO_PARSE_RETRIES)
    for attempt in range(retries + 1):
        prompt = _build_prompt(raw_text=raw_text, context=context, strict_error=validation_error)
        try:
            raw, usage_tokens = _call_openai_todo(prompt, settings.TODO_PARSER_MODEL, settings.OPENAI_API_KEY)
            tokens = usage_tokens if usage_tokens is not None else tokens
            payload = json.loads(raw)
            draft = TodoDraft.model_validate(payload)
            record_parse(True)
            log_run_event(
                flow="todo_parse",
                trace_id=trace_id,
                prompt_version=settings.PROMPT_VERSION,
                tokens=tokens,
                latency_ms=int((time.perf_counter() - start) * 1000),
                tool_success=True,
                validation_errors=None,
                confidence=draft.confidence,
                extra={"attempt": attempt + 1},
            )
            return draft
        except (URLError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            validation_error = str(exc)
            logger.warning("todo.parse_failed attempt=%s error=%s", attempt + 1, validation_error)
            if attempt < retries:
                record_retry("todo_parse", validation_error)

    record_parse(False)
    log_run_event(
        flow="todo_parse",
        trace_id=trace_id,
        prompt_version=settings.PROMPT_VERSION,
        tokens=tokens,
        latency_ms=int((time.perf_counter() - start) * 1000),
        tool_success=False,
        validation_errors=validation_error,
        confidence=0.0,
        extra={"attempts": retries + 1},
    )
    return _rule_todo(raw_text, context)
