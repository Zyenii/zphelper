from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from personal_ops_agent.commute.location_extractor import extract_locations_llm


@dataclass(frozen=True)
class TripContext:
    origin_text: str
    destination_text: str
    departure_time: datetime
    event_start_time: datetime | None
    event_title: str | None
    used_calendar_destination: bool
    needs_clarification: bool
    clarification_question: str | None


def _get_tz(timezone_name: str):
    if timezone_name.upper() == "UTC":
        return timezone.utc
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return timezone.utc


def _parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _next_event(calendar_state: dict, now_local: datetime) -> dict | None:
    events = calendar_state.get("events", [])
    if not events:
        return None
    ordered = sorted(events, key=lambda item: _parse_iso(item["start"]))
    for event in ordered:
        start = _parse_iso(event["start"])
        if start.tzinfo:
            start = start.astimezone(now_local.tzinfo)
        if start > now_local:
            return event
    return ordered[0]


def _extract_destination(message: str) -> str | None:
    lowered = message.lower()
    zh_patterns = [
        r"(?:去|到)\s*([^，。!?？]{2,120}?)(?=(?:要多久|多久|多长时间|吗|呢|吧|[，。!?？]|$))",
    ]
    en_patterns = [
        r"(?:to)\s+([a-z0-9][a-z0-9\s,'&-]{1,100}?)(?=\s+how\s+long\b|\s*\?|$)",
        r"(?:get\s+to|go\s+to)\s+([a-z0-9][a-z0-9\s,'&-]{1,100}?)(?=\s+how\s+long\b|\s*\?|$)",
    ]
    for pattern in zh_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            value = match.group(1).strip(" ,，。.?？!")
            if value:
                return value
    for pattern in en_patterns:
        match = re.search(pattern, lowered, re.IGNORECASE)
        if match:
            value = match.group(1).strip(" ,，。.?？!")
            if value:
                return value
    return None


def _extract_origin(message: str) -> str | None:
    lowered = message.lower()
    patterns = [
        r"从\s*([^，。!?？]{2,120}?)(?=(?:出发|走|去|到|[，。!?？]|$))",
        r"from\s+([a-z0-9][a-z0-9\s,'&-]{1,100}?)(?=\s+to\b|\s+for\b|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, message if "从" in pattern else lowered, re.IGNORECASE)
        if match:
            value = match.group(1).strip(" ,，。.?？!")
            if value:
                return value
    return None


def _extract_departure_time(message: str, now_local: datetime) -> datetime | None:
    lowered = message.lower()
    day_offset = 0
    if "tomorrow" in lowered or "明天" in message:
        day_offset = 1
    elif "后天" in message:
        day_offset = 2

    match_zh_half = re.search(r"(\d{1,2})点半", message)
    if match_zh_half:
        hour = int(match_zh_half.group(1))
        hour = hour + 12 if ("下午" in message or "晚上" in message) and hour < 12 else hour
        return datetime.combine(now_local.date() + timedelta(days=day_offset), time(hour=hour, minute=30), tzinfo=now_local.tzinfo)

    match_zh = re.search(r"(\d{1,2})点(?:(\d{1,2})分)?", message)
    if match_zh:
        hour = int(match_zh.group(1))
        minute = int(match_zh.group(2) or 0)
        hour = hour + 12 if ("下午" in message or "晚上" in message) and hour < 12 else hour
        return datetime.combine(now_local.date() + timedelta(days=day_offset), time(hour=hour, minute=minute), tzinfo=now_local.tzinfo)

    match_en = re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", lowered)
    if match_en:
        hour = int(match_en.group(1))
        minute = int(match_en.group(2) or 0)
        ampm = match_en.group(3)
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        return datetime.combine(now_local.date() + timedelta(days=day_offset), time(hour=hour, minute=minute), tzinfo=now_local.tzinfo)

    return None


def _resolve_place_alias(value: str | None, memory_state: dict | None) -> str | None:
    if not value:
        return value
    aliases = (memory_state or {}).get("place_aliases", {})
    if not isinstance(aliases, dict):
        return value
    normalized = value.strip()
    alias = aliases.get(normalized) or aliases.get(normalized.lower())
    return str(alias).strip() if isinstance(alias, str) and alias.strip() else value


def resolve_trip_context(
    message: str,
    intent: str,
    calendar_state: dict,
    now_utc: datetime,
    timezone_name: str,
    default_origin: str,
    memory_state: dict | None = None,
) -> TripContext:
    local_tz = _get_tz(timezone_name)
    now_local = now_utc.astimezone(local_tz)
    next_event = _next_event(calendar_state=calendar_state, now_local=now_local)

    explicit_destination = _extract_destination(message)
    explicit_origin = _extract_origin(message)
    if not explicit_destination:
        llm_locations = extract_locations_llm(message)
        if llm_locations:
            explicit_destination = llm_locations.destination or explicit_destination
            explicit_origin = llm_locations.origin or explicit_origin
    calendar_destination = _resolve_place_alias((next_event or {}).get("location"), memory_state)
    destination = _resolve_place_alias(explicit_destination, memory_state) or calendar_destination
    used_calendar_destination = bool(destination and not explicit_destination and calendar_destination)

    if not destination:
        return TripContext(
            origin_text=_resolve_place_alias(explicit_origin or default_origin, memory_state) or default_origin,
            destination_text="",
            departure_time=now_local,
            event_start_time=None,
            event_title=(next_event or {}).get("title"),
            used_calendar_destination=False,
            needs_clarification=True,
            clarification_question="你要去哪里？请告诉我目的地。",
        )

    profile = (memory_state or {}).get("user_profile", {})
    memory_home = profile.get("home_location") if isinstance(profile, dict) else None
    origin = _resolve_place_alias(explicit_origin or memory_home or default_origin, memory_state) or default_origin
    departure_time = _extract_departure_time(message, now_local) or now_local

    event_start_local = None
    if next_event and next_event.get("start"):
        event_start = _parse_iso(next_event["start"])
        event_start_local = event_start.astimezone(local_tz) if event_start.tzinfo else event_start.replace(tzinfo=local_tz)

    return TripContext(
        origin_text=origin,
        destination_text=destination,
        departure_time=departure_time,
        event_start_time=event_start_local,
        event_title=(next_event or {}).get("title"),
        used_calendar_destination=used_calendar_destination,
        needs_clarification=False,
        clarification_question=None,
    )
