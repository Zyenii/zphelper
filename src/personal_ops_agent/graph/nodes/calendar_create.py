from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from personal_ops_agent.calendar.time_parser import parse_calendar_datetime_llm, parse_calendar_datetime_rule
from personal_ops_agent.connectors.google_calendar import CalendarConnectorError, create_calendar_event
from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.graph.state import AgentState


def _extract_title(message: str) -> str:
    text = re.sub(r"(20\d{2}-\d{2}-\d{2}[ T]\d{2}:\d{2})", "", message)
    text = re.sub(
        r"\b(create event|add event|add to calendar|schedule a meeting)\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"(创建日程|添加日程|加到日历|安排会议)", "", text)
    text = re.sub(r"\bat\s+[a-zA-Z0-9][a-zA-Z0-9 ,'-]{2,80}$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"在\s*[^\s，。,.!?？]{2,60}$", "", text)
    return text.strip(" :，,。")


def _extract_location(message: str) -> str | None:
    match = re.search(r"\bat\s+([a-zA-Z0-9][a-zA-Z0-9 ,'-]{2,80})$", message, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match_zh = re.search(r"在\s*([^\s，。,.!?？]{2,60})$", message)
    if match_zh:
        return match_zh.group(1).strip()
    return None


def calendar_create_node(state: AgentState) -> AgentState:
    settings = get_settings()
    message = state.get("user_message", "")
    try:
        tz = ZoneInfo(settings.DEFAULT_TIMEZONE)
    except ZoneInfoNotFoundError:
        tz = timezone.utc
    now_local = datetime.now(timezone.utc).astimezone(tz)

    parsed_time = parse_calendar_datetime_rule(message=message, now_local=now_local)
    if parsed_time is None:
        parsed_time = parse_calendar_datetime_llm(message=message, now_local=now_local, timezone_name=settings.DEFAULT_TIMEZONE)

    if parsed_time is None:
        return {
            "calendar_write": {
                "success": False,
                "needs_clarification": True,
                "clarification_question": "请提供时间，例如“明天晚上7点半”或“2026-03-01 14:00”。",
            },
            "output": "我可以帮你创建日历事件，请提供时间（支持“明天晚上7点半”或 YYYY-MM-DD HH:MM）。",
        }

    start = parsed_time.start
    end = parsed_time.end

    title = _extract_title(message)
    if not title:
        title = "New Event"
    location = _extract_location(message)

    try:
        created = create_calendar_event(
            summary=title,
            start_iso=start.astimezone(timezone.utc).isoformat(),
            end_iso=end.astimezone(timezone.utc).isoformat(),
            timezone_name=settings.DEFAULT_TIMEZONE,
            location=location,
        )
    except CalendarConnectorError as exc:
        return {
            "calendar_write": {"success": False, "error": str(exc)},
            "output": f"Calendar create failed: {exc}",
        }

    if created.get("created"):
        output = (
            f"Created event {created.get('summary')} from {created.get('start')} to {created.get('end')}. "
            f"event_id={created.get('event_id')} (time_source={parsed_time.source})"
        )
    else:
        output = (
            f"Duplicate detected. Reused existing event {created.get('summary')} "
            f"event_id={created.get('event_id')} (time_source={parsed_time.source})"
        )
    return {"calendar_write": {"success": True, **created}, "output": output}
