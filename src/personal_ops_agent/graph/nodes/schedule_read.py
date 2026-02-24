from __future__ import annotations

import logging

from personal_ops_agent.connectors.google_calendar import CalendarConnectorError, get_calendar_events
from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.graph.state import AgentState
from personal_ops_agent.timewindow.llm import parse_time_window_llm
from personal_ops_agent.timewindow.rules import (
    default_today_window,
    needs_time_window,
    parse_time_window_rule,
    resolve_now_local,
)

logger = logging.getLogger(__name__)


def schedule_read_node(state: AgentState) -> AgentState:
    settings = get_settings()
    message = state.get("user_message", "")
    intent = state.get("intent", "unknown")
    timezone_name = settings.DEFAULT_TIMEZONE
    now_local = resolve_now_local(timezone_name=timezone_name, now_override_iso=settings.TIMEWINDOW_NOW_ISO)

    selected_window = None
    if needs_time_window(intent):
        selected_window = parse_time_window_rule(message=message, now_local=now_local, timezone_name=timezone_name)
        if selected_window is None:
            selected_window = parse_time_window_llm(message=message, now_local=now_local, timezone_name=timezone_name)
    if selected_window is None:
        selected_window = default_today_window(now_local=now_local, timezone_name=timezone_name)

    logger.info(
        "timewindow.selected source=%s granularity=%s confidence=%s",
        selected_window.source,
        selected_window.granularity,
        selected_window.confidence,
    )

    window_start = selected_window.start_utc
    window_end = selected_window.end_utc
    calendar_state: dict[str, object] = {
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "window_tz": selected_window.tz,
        "window_source": selected_window.source,
        "window_granularity": selected_window.granularity,
        "window_confidence": selected_window.confidence,
        "events": [],
    }

    try:
        events = get_calendar_events(window_start=window_start, window_end=window_end)
        calendar_state["events"] = events
    except CalendarConnectorError as exc:
        error_message = str(exc)
        logger.error("schedule_read.failed error=%s", error_message)
        calendar_state["error"] = error_message

    return {"calendar": calendar_state}
