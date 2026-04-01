from __future__ import annotations

from datetime import datetime

from personal_ops_agent.memory.schemas import PersonalMemory


def build_planner_memory_context(memory: PersonalMemory) -> dict[str, object]:
    profile = memory.user_profile
    preferences = memory.preferences
    return {
        "user_profile": {
            "default_timezone": profile.default_timezone,
            "home_location": profile.home_location,
            "preferred_transport_mode": profile.preferred_transport_mode,
            "default_calendar_id": profile.default_calendar_id,
        },
        "preferences": {
            "rain_alert_threshold": preferences.rain_alert_threshold,
            "cold_alert_celsius": preferences.cold_alert_celsius,
            "extra_buffer_minutes": preferences.extra_buffer_minutes,
        },
        "place_aliases": memory.place_aliases,
        "behavioral_notes": memory.behavioral_notes.model_dump(),
    }


def build_planner_context(
    *,
    user_message: str,
    memory: PersonalMemory,
    now_utc: datetime,
    continuation: dict[str, object] | None = None,
) -> dict[str, object]:
    context = {
        "user_message": user_message,
        "current_time_utc": now_utc.isoformat(),
        "available_tools": [
            "schedule_read",
            "schedule_summarize",
            "weather_read",
            "weather_summarize",
            "commute_plan",
            "todo_read",
            "todo_parse",
            "todo_write",
            "checklist_generate",
            "calendar_create",
        ],
        "memory": build_planner_memory_context(memory),
    }
    if continuation:
        context["continuation_context"] = continuation
    return context
