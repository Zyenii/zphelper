from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from personal_ops_agent.checklist.schemas import LeavingChecklist
from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.core.telemetry import record_llm_usage, record_retry
from personal_ops_agent.eval.postgres_logger import log_run_event

logger = logging.getLogger(__name__)


def _next_event(calendar_state: dict[str, Any]) -> dict[str, Any] | None:
    events = calendar_state.get("events", [])
    if not events:
        return None
    return sorted(events, key=lambda item: item.get("start", ""))[0]


def _deterministic_items(
    event: dict[str, Any] | None,
    weather_state: dict[str, Any],
    commute_state: dict[str, Any],
) -> tuple[list[str], list[str]]:
    items: list[str] = []
    reasons: list[str] = []
    points = weather_state.get("points", [])
    rain_max = max((int(point.get("rain_probability", 0)) for point in points), default=0)
    temp_min = min((float(point.get("apparent_temperature", 99.0)) for point in points), default=99.0)
    transport_mode = str(commute_state.get("recommendation", {}).get("transport_mode", ""))
    title = str((event or {}).get("title", "")).lower()

    if rain_max >= 50:
        items.append("Umbrella")
        reasons.append(f"Rain probability reaches {rain_max}% in your travel window.")
    if temp_min <= 3:
        items.append("Warm coat and gloves")
        reasons.append(f"Feels-like temperature drops to {temp_min:.1f}C.")
    if transport_mode in {"transit", "taxi"}:
        items.append("Transit card / ride-share app ready")
        reasons.append(f"Recommended transport mode is {transport_mode}.")
    if any(keyword in title for keyword in ("presentation", "interview", "exam")):
        items.append("ID / badge")
        reasons.append("High-stakes event typically requires identity check.")
        items.append("Laptop and charger")
        reasons.append("Event type suggests materials may be needed.")

    if not items:
        items = ["Phone", "Wallet", "Keys"]
        reasons = ["Core essentials for any trip."] * 3
    return items[:10], reasons[:10]


def _build_summary(
    event: dict[str, Any] | None,
    commute_state: dict[str, Any],
) -> str:
    if not event:
        return "No upcoming event found. Keep essentials ready and re-check schedule."
    title = event.get("title", "Next event")
    start = event.get("start", "")
    location = event.get("location", "unknown location")
    leave_time = commute_state.get("recommendation", {}).get("leave_time")
    leave_text = leave_time if isinstance(leave_time, str) else "N/A"
    return f"{title} at {start} in {location}. Suggested leave time: {leave_text}."


def _build_prompt(context: dict[str, Any], current: LeavingChecklist, error_text: str | None = None) -> str:
    strict = f"\nPrevious validation error: {error_text}\nFix exactly." if error_text else ""
    return (
        "You are a leaving checklist generator.\n"
        "Return strict JSON only with keys: summary, items, reasons, confidence.\n"
        "items and reasons must be same length and non-empty. Max 12 items.\n"
        "Do not include markdown.\n"
        f"Context: {json.dumps(context, ensure_ascii=False)}\n"
        f"Current deterministic baseline: {current.model_dump_json()}\n"
        f"{strict}"
    )


def _call_openai(prompt: str, model: str, api_key: str) -> tuple[str, int | None]:
    req = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(
            {"model": model, "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}]}
        ).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    started_at = time.perf_counter()
    with urlopen(req, timeout=15) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    record_llm_usage(model=model, usage=payload.get("usage"), latency_ms=latency_ms)
    usage = payload.get("usage", {})
    tokens = usage.get("total_tokens") if isinstance(usage, dict) else None
    output = payload.get("output", [])
    for item in output:
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return str(content.get("text", "")), tokens if isinstance(tokens, int) else None
    text = payload.get("output_text")
    if isinstance(text, str):
        return text, tokens if isinstance(tokens, int) else None
    raise ValueError("No output text found in checklist LLM response")


def generate_checklist(
    *,
    trace_id: str | None,
    calendar_state: dict[str, Any],
    weather_state: dict[str, Any],
    commute_state: dict[str, Any],
) -> LeavingChecklist:
    settings = get_settings()
    start = time.perf_counter()
    event = _next_event(calendar_state)
    items, reasons = _deterministic_items(event=event, weather_state=weather_state, commute_state=commute_state)
    base = LeavingChecklist(summary=_build_summary(event, commute_state), items=items, reasons=reasons, confidence=0.75)
    base.validate_alignment()

    if not settings.OPENAI_API_KEY:
        return base

    context = {
        "event": event or {},
        "weather": weather_state,
        "commute": commute_state,
    }
    error_text: str | None = None
    tokens: int | None = None
    retries = max(0, settings.CHECKLIST_RETRIES)
    for attempt in range(retries + 1):
        try:
            raw, usage_tokens = _call_openai(
                _build_prompt(context=context, current=base, error_text=error_text),
                settings.CHECKLIST_MODEL,
                settings.OPENAI_API_KEY,
            )
            tokens = usage_tokens if usage_tokens is not None else tokens
            candidate = LeavingChecklist.model_validate(json.loads(raw))
            candidate.validate_alignment()
            if candidate.confidence < settings.CHECKLIST_CONFIDENCE_THRESHOLD:
                return base
            log_run_event(
                flow="checklist_generate",
                trace_id=trace_id,
                prompt_version=settings.PROMPT_VERSION,
                tokens=tokens,
                latency_ms=int((time.perf_counter() - start) * 1000),
                tool_success=True,
                validation_errors=None,
                confidence=candidate.confidence,
                extra={"attempt": attempt + 1},
            )
            return candidate
        except (URLError, ValidationError, ValueError, json.JSONDecodeError) as exc:
            error_text = str(exc)
            logger.warning("checklist.llm_failed attempt=%s error=%s", attempt + 1, error_text)
            if attempt < retries:
                record_retry("checklist_generate", error_text)

    log_run_event(
        flow="checklist_generate",
        trace_id=trace_id,
        prompt_version=settings.PROMPT_VERSION,
        tokens=tokens,
        latency_ms=int((time.perf_counter() - start) * 1000),
        tool_success=False,
        validation_errors=error_text,
        confidence=base.confidence,
        extra={"fallback": "deterministic"},
    )
    return base
