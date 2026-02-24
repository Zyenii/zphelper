from __future__ import annotations

import re
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from personal_ops_agent.router.intent import Intent
from personal_ops_agent.timewindow.types import TimeWindow


def needs_time_window(intent: str) -> bool:
    return (
        intent == Intent.SCHEDULE_SUMMARY.value
        or intent.startswith("schedule_")
        or intent == Intent.WEATHER_SUMMARY.value
        or intent.startswith("weather_")
    )


def get_timezone(timezone_name: str, now_override_iso: str | None = None):
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        if now_override_iso:
            value = now_override_iso
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is not None:
                return parsed.tzinfo
        return timezone.utc


def resolve_now_local(timezone_name: str, now_override_iso: str | None = None) -> datetime:
    tz = get_timezone(timezone_name, now_override_iso=now_override_iso)
    if now_override_iso:
        value = now_override_iso
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=tz)
        return parsed.astimezone(tz)
    return datetime.now(timezone.utc).astimezone(tz)


def _window_from_local_bounds(
    start_local: datetime,
    end_local: datetime,
    timezone_name: str,
    granularity: str,
    source: str,
    confidence: float | None = None,
    reason: str | None = None,
) -> TimeWindow:
    return TimeWindow(
        start_utc=start_local.astimezone(timezone.utc),
        end_utc=end_local.astimezone(timezone.utc),
        tz=timezone_name,
        granularity=granularity,  # type: ignore[arg-type]
        source=source,  # type: ignore[arg-type]
        confidence=confidence,
        reason=reason,
    )


def _resolve_day_of_month(now_local: datetime, day_of_month: int) -> datetime.date | None:
    if day_of_month < 1 or day_of_month > 31:
        return None
    year = now_local.year
    month = now_local.month
    try:
        candidate = datetime(year=year, month=month, day=day_of_month).date()
    except ValueError:
        candidate = None
    if candidate and candidate >= now_local.date():
        return candidate

    month += 1
    if month > 12:
        month = 1
        year += 1
    try:
        return datetime(year=year, month=month, day=day_of_month).date()
    except ValueError:
        return None


def _period_bounds(target_date, now_local: datetime, message: str, lowered: str):
    tzinfo = now_local.tzinfo
    if "morning" in lowered or "上午" in message:
        return (
            datetime.combine(target_date, time(hour=8), tzinfo=tzinfo),
            datetime.combine(target_date, time(hour=12), tzinfo=tzinfo),
            "range",
        )
    if "afternoon" in lowered or "下午" in message:
        return (
            datetime.combine(target_date, time(hour=12), tzinfo=tzinfo),
            datetime.combine(target_date, time(hour=18), tzinfo=tzinfo),
            "range",
        )
    if "evening" in lowered or "晚上" in message:
        return (
            datetime.combine(target_date, time(hour=18), tzinfo=tzinfo),
            datetime.combine(target_date, time(hour=22), tzinfo=tzinfo),
            "range",
        )
    if "tonight" in lowered or "今晚" in message:
        start = now_local
        evening_start = datetime.combine(target_date, time(hour=18), tzinfo=tzinfo)
        if start < evening_start:
            start = evening_start
        end = datetime.combine(target_date, time(hour=22), tzinfo=tzinfo)
        return (start, end, "range")
    return (
        datetime.combine(target_date, time.min, tzinfo=tzinfo),
        datetime.combine(target_date, time.min, tzinfo=tzinfo) + timedelta(days=1),
        "day",
    )


def default_today_window(now_local: datetime, timezone_name: str) -> TimeWindow:
    start = datetime.combine(now_local.date(), time.min, tzinfo=now_local.tzinfo)
    end = start + timedelta(days=1)
    return _window_from_local_bounds(start, end, timezone_name, "day", "default")


def parse_time_window_rule(message: str, now_local: datetime, timezone_name: str) -> TimeWindow | None:
    lowered = message.lower()
    today_start = datetime.combine(now_local.date(), time.min, tzinfo=now_local.tzinfo)

    day_of_month_match = re.search(r"(\d{1,2})号", message)
    if day_of_month_match:
        resolved_date = _resolve_day_of_month(now_local, int(day_of_month_match.group(1)))
        if resolved_date is not None:
            start, end, granularity = _period_bounds(resolved_date, now_local, message, lowered)
            return _window_from_local_bounds(start, end, timezone_name, granularity, "rule")

    if "today" in lowered or "今天" in message:
        return _window_from_local_bounds(today_start, today_start + timedelta(days=1), timezone_name, "day", "rule")

    if "tomorrow" in lowered or "明天" in message:
        start = today_start + timedelta(days=1)
        return _window_from_local_bounds(start, start + timedelta(days=1), timezone_name, "day", "rule")

    if "后天" in message:
        start = today_start + timedelta(days=2)
        return _window_from_local_bounds(start, start + timedelta(days=1), timezone_name, "day", "rule")

    # Day periods
    if any(item in lowered or item in message for item in ("morning", "上午", "afternoon", "下午", "evening", "晚上", "tonight", "今晚")):
        target_date = now_local.date()
        if "tomorrow" in lowered or "明天" in message:
            target_date = target_date + timedelta(days=1)
        if "后天" in message:
            target_date = target_date + timedelta(days=2)
        start, end, granularity = _period_bounds(target_date, now_local, message, lowered)
        return _window_from_local_bounds(start, end, timezone_name, granularity, "rule")

    if "weekend" in lowered or "周末" in message:
        week_start = today_start - timedelta(days=today_start.weekday())
        saturday = week_start + timedelta(days=5)
        monday = week_start + timedelta(days=7)
        return _window_from_local_bounds(saturday, monday, timezone_name, "range", "rule")

    if "this week" in lowered or "本周" in message or "这周" in message:
        start = today_start - timedelta(days=today_start.weekday())
        return _window_from_local_bounds(start, start + timedelta(days=7), timezone_name, "week", "rule")

    if "next week" in lowered or "下周" in message:
        start = today_start - timedelta(days=today_start.weekday()) + timedelta(days=7)
        return _window_from_local_bounds(start, start + timedelta(days=7), timezone_name, "week", "rule")

    days_match = re.search(r"next\s+(\d{1,2})\s+days", lowered)
    if not days_match:
        days_match = re.search(r"(未来|接下来)\s*(\d{1,2})\s*天", message)
    if days_match:
        raw_days = days_match.group(1 if "next" in lowered else 2)
        days = int(raw_days)
        if 1 <= days <= 14:
            return _window_from_local_bounds(
                today_start,
                today_start + timedelta(days=days),
                timezone_name,
                "range",
                "rule",
            )

    return None
