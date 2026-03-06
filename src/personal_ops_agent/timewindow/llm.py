from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.core.telemetry import record_llm_usage
from personal_ops_agent.timewindow.types import TimeWindow

logger = logging.getLogger(__name__)


class LLMTimeWindowOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_local: str
    end_local: str
    timezone: str
    confidence: float
    reason: str

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        if not (0.0 <= value <= 1.0):
            raise ValueError("confidence must be within [0,1]")
        return value


def build_timewindow_prompt(now_local_iso: str, timezone_name: str) -> str:
    return (
        "You are a time range extractor for calendar queries.\n"
        "Output strict JSON only. No markdown.\n"
        f"Reference now(local): {now_local_iso}\n"
        f"Default timezone: {timezone_name}\n"
        "Output schema:\n"
        '{"start_local":"YYYY-MM-DDTHH:MM:SS","end_local":"YYYY-MM-DDTHH:MM:SS","timezone":"IANA_TZ","confidence":0.0,"reason":"short"}\n'
        "Rules:\n"
        "- Extract only time window. Never create events.\n"
        "- morning/上午 => 08:00-12:00\n"
        "- afternoon/下午 => 12:00-18:00\n"
        "- evening/晚上 => 18:00-22:00\n"
        "- tonight/今晚 => now..22:00 (or 18:00..22:00 if now earlier)\n"
        "- next N days / 未来N天 / 接下来N天 => [today 00:00, today+N days 00:00)\n"
        "- If ambiguous, provide best-effort with low confidence.\n"
        "Examples:\n"
        'Input: "下周三下午我忙吗" -> {"start_local":"2026-02-25T12:00:00","end_local":"2026-02-25T18:00:00","timezone":"America/New_York","confidence":0.84,"reason":"下周三下午"}\n'
        'Input: "Can you show my schedule for the next 3 days?" -> {"start_local":"2026-02-18T00:00:00","end_local":"2026-02-21T00:00:00","timezone":"America/New_York","confidence":0.9,"reason":"next 3 days range"}\n'
        'Input: "这周末有什么安排" -> {"start_local":"2026-02-21T00:00:00","end_local":"2026-02-23T00:00:00","timezone":"America/New_York","confidence":0.88,"reason":"周末范围"}'
    )


def _call_openai_timewindow(message: str, model: str, api_key: str, now_local_iso: str, timezone_name: str) -> str:
    prompt = build_timewindow_prompt(now_local_iso=now_local_iso, timezone_name=timezone_name)
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": prompt}]},
            {"role": "user", "content": [{"type": "input_text", "text": message}]},
        ],
    }
    req = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        started_at = time.perf_counter()
        with urlopen(req, timeout=12) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(f"Time-window LLM network error: {exc}") from exc
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    record_llm_usage(model=model, usage=payload.get("usage"), latency_ms=latency_ms)

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
    raise RuntimeError("No LLM time-window output text found")


def parse_time_window_llm(message: str, now_local: datetime, timezone_name: str) -> TimeWindow | None:
    settings = get_settings()
    if not (settings.LLM_TIMEWINDOW and settings.OPENAI_API_KEY):
        return None

    try:
        raw = _call_openai_timewindow(
            message=message,
            model=settings.LLM_TIMEWINDOW_MODEL,
            api_key=settings.OPENAI_API_KEY,
            now_local_iso=now_local.replace(microsecond=0).isoformat(),
            timezone_name=timezone_name,
        )
        payload = json.loads(raw)
        validated = LLMTimeWindowOutput.model_validate(payload)
        if validated.confidence < settings.LLM_TIMEWINDOW_THRESHOLD:
            return None

        try:
            output_tz = ZoneInfo(validated.timezone)
        except ZoneInfoNotFoundError:
            output_tz = now_local.tzinfo or timezone.utc
        start_local = datetime.fromisoformat(validated.start_local)
        end_local = datetime.fromisoformat(validated.end_local)
        if start_local.tzinfo is None:
            start_local = start_local.replace(tzinfo=output_tz)
        else:
            start_local = start_local.astimezone(output_tz)
        if end_local.tzinfo is None:
            end_local = end_local.replace(tzinfo=output_tz)
        else:
            end_local = end_local.astimezone(output_tz)
        if end_local <= start_local:
            return None

        return TimeWindow(
            start_utc=start_local.astimezone(timezone.utc),
            end_utc=end_local.astimezone(timezone.utc),
            tz=validated.timezone,
            granularity="range",
            source="llm",
            confidence=validated.confidence,
            reason=validated.reason,
        )
    except (RuntimeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        logger.warning("timewindow.llm_failed error=%s", exc)
        return None
