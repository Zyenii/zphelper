from __future__ import annotations

import logging
from datetime import datetime, time, timedelta, timezone

from personal_ops_agent.connectors.google_calendar import CalendarConnectorError, get_calendar_events
from personal_ops_agent.graph.state import AgentState

logger = logging.getLogger(__name__)


def _resolve_window(user_message: str) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    target_date = now.date()

    lowered = user_message.lower()
    if "tomorrow" in lowered or "明天" in user_message:
        target_date = target_date + timedelta(days=1)

    start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return start, end


def schedule_read_node(state: AgentState) -> AgentState:
    message = state.get("user_message", "")
    window_start, window_end = _resolve_window(message)
    calendar_state: dict[str, object] = {
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
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
