from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.core.telemetry import record_llm_usage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CalendarDateTimeParse:
    start: datetime
    end: datetime
    source: str
    confidence: float | None = None


class CalendarDateTimeLLMOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_local: str
    end_local: str
    timezone: str
    confidence: float
    rationale: str

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        if not (0.0 <= value <= 1.0):
            raise ValueError("confidence must be in [0,1]")
        return value


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


def _build_llm_prompt(message: str, now_local: datetime, timezone_name: str) -> str:
    return (
        "You extract calendar event start/end datetimes from user text.\n"
        "Output strict JSON only with keys:\n"
        '{"start_local":"YYYY-MM-DDTHH:MM:SS","end_local":"YYYY-MM-DDTHH:MM:SS","timezone":"IANA","confidence":0.0,"rationale":"short"}\n'
        "Rules:\n"
        "- Chinese/English supported.\n"
        "- evening/晚上 default starts 19:00 if time not explicit.\n"
        "- morning/上午 default starts 09:00 if time not explicit.\n"
        "- afternoon/下午 default starts 15:00 if time not explicit.\n"
        "- Default duration is 1 hour if end time not inferable.\n"
        "- If uncertain, return low confidence.\n"
        f"Reference now(local): {now_local.replace(microsecond=0).isoformat()} timezone={timezone_name}\n"
        f"User: {message}"
    )


def _call_openai_calendar_time(message: str, now_local: datetime, timezone_name: str) -> str:
    settings = get_settings()
    prompt = _build_llm_prompt(message=message, now_local=now_local, timezone_name=timezone_name)
    body = {
        "model": settings.LLM_CALENDAR_CREATE_MODEL,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
    }
    req = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=12) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(f"Calendar time parse network error: {exc}") from exc
    record_llm_usage(model=settings.LLM_CALENDAR_CREATE_MODEL, usage=payload.get("usage"))
    return _extract_text_from_openai_response(payload)


def _day_offset(message: str) -> int:
    lowered = message.lower()
    if "后天" in message or "day after tomorrow" in lowered:
        return 2
    if "明天" in message or "tomorrow" in lowered:
        return 1
    return 0


def _extract_time_component(message: str) -> tuple[int, int] | None:
    lowered = message.lower()

    match_half = re.search(r"(\d{1,2})点半", message)
    if match_half:
        hour = int(match_half.group(1))
        if ("下午" in message or "晚上" in message) and hour < 12:
            hour += 12
        return hour, 30

    match_zh = re.search(r"(\d{1,2})点(?:(\d{1,2})分)?", message)
    if match_zh:
        hour = int(match_zh.group(1))
        minute = int(match_zh.group(2) or 0)
        if ("下午" in message or "晚上" in message) and hour < 12:
            hour += 12
        return hour, minute

    match_en = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", lowered)
    if match_en:
        hour = int(match_en.group(1))
        minute = int(match_en.group(2) or 0)
        ampm = match_en.group(3)
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        return hour, minute

    return None


def parse_calendar_datetime_rule(message: str, now_local: datetime) -> CalendarDateTimeParse | None:
    matches = re.findall(r"(20\d{2}-\d{2}-\d{2}[ T]\d{2}:\d{2})", message)
    if matches:
        parsed = []
        for item in matches:
            dt = datetime.fromisoformat(item.replace(" ", "T"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=now_local.tzinfo)
            parsed.append(dt)
        start = parsed[0]
        end = parsed[1] if len(parsed) > 1 else (start + timedelta(hours=1))
        if end <= start:
            end = start + timedelta(hours=1)
        return CalendarDateTimeParse(start=start, end=end, source="rule", confidence=1.0)

    offset = _day_offset(message)
    time_component = _extract_time_component(message)
    lowered = message.lower()
    if time_component is None and not any(
        token in lowered or token in message for token in ("上午", "下午", "晚上", "morning", "afternoon", "evening", "tonight")
    ):
        return None

    target_date = now_local.date() + timedelta(days=offset)
    if time_component is None:
        if "上午" in message or "morning" in lowered:
            time_component = (9, 0)
        elif "下午" in message or "afternoon" in lowered:
            time_component = (15, 0)
        else:
            time_component = (19, 0)

    start = datetime(
        year=target_date.year,
        month=target_date.month,
        day=target_date.day,
        hour=time_component[0],
        minute=time_component[1],
        tzinfo=now_local.tzinfo,
    )
    end = start + timedelta(hours=1)
    return CalendarDateTimeParse(start=start, end=end, source="rule", confidence=0.9)


def parse_calendar_datetime_llm(message: str, now_local: datetime, timezone_name: str) -> CalendarDateTimeParse | None:
    settings = get_settings()
    if not (settings.LLM_CALENDAR_CREATE_TIME and settings.OPENAI_API_KEY):
        return None
    try:
        raw = _call_openai_calendar_time(message=message, now_local=now_local, timezone_name=timezone_name)
        payload = json.loads(raw)
        validated = CalendarDateTimeLLMOutput.model_validate(payload)
        if validated.confidence < settings.LLM_CALENDAR_CREATE_THRESHOLD:
            return None
        try:
            out_tz = ZoneInfo(validated.timezone)
        except ZoneInfoNotFoundError:
            out_tz = now_local.tzinfo or timezone.utc
        start = datetime.fromisoformat(validated.start_local)
        end = datetime.fromisoformat(validated.end_local)
        if start.tzinfo is None:
            start = start.replace(tzinfo=out_tz)
        else:
            start = start.astimezone(out_tz)
        if end.tzinfo is None:
            end = end.replace(tzinfo=out_tz)
        else:
            end = end.astimezone(out_tz)
        if end <= start:
            return None
        return CalendarDateTimeParse(start=start, end=end, source="llm", confidence=validated.confidence)
    except (RuntimeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        logger.warning("calendar_time.llm_failed error=%s", exc)
        return None
