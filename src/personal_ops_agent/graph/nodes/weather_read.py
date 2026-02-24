from __future__ import annotations

import logging
from datetime import timedelta

from personal_ops_agent.connectors.weather import WeatherConnectorError, get_weather
from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.graph.state import AgentState
from personal_ops_agent.timewindow.llm import parse_time_window_llm
from personal_ops_agent.timewindow.rules import (
    default_today_window,
    needs_time_window,
    parse_time_window_rule,
    resolve_now_local,
)
from personal_ops_agent.timewindow.types import TimeWindow

logger = logging.getLogger(__name__)


def weather_read_node(state: AgentState) -> AgentState:
    settings = get_settings()
    intent = state.get("intent", "unknown")
    message = state.get("user_message", "")
    timezone_name = settings.DEFAULT_TIMEZONE
    now_local = resolve_now_local(timezone_name=timezone_name, now_override_iso=settings.TIMEWINDOW_NOW_ISO)

    selected_window = None
    if intent == "commute_advice":
        start = now_local
        end = now_local + timedelta(hours=max(1, settings.WEATHER_FORECAST_HOURS))
        selected_window = TimeWindow(
            start_utc=start.astimezone(start.tzinfo),
            end_utc=end.astimezone(end.tzinfo),
            tz=timezone_name,
            granularity="range",
            source="default",
        )
    elif needs_time_window(intent):
        selected_window = parse_time_window_rule(message=message, now_local=now_local, timezone_name=timezone_name)
        if selected_window is None:
            selected_window = parse_time_window_llm(message=message, now_local=now_local, timezone_name=timezone_name)
        if selected_window is None:
            selected_window = default_today_window(now_local=now_local, timezone_name=timezone_name)
    else:
        selected_window = default_today_window(now_local=now_local, timezone_name=timezone_name)

    weather_state: dict[str, object] = {
        "summary": "",
        "points": [],
        "window_start": selected_window.start_utc.isoformat(),
        "window_end": selected_window.end_utc.isoformat(),
        "window_tz": selected_window.tz,
        "window_source": selected_window.source,
        "window_granularity": selected_window.granularity,
        "window_confidence": selected_window.confidence,
    }
    try:
        payload = get_weather(
            window_start_utc=selected_window.start_utc,
            window_end_utc=selected_window.end_utc,
            timezone_name=selected_window.tz,
            hours=settings.WEATHER_FORECAST_HOURS,
        )
        weather_state["summary"] = payload.get("summary", "")
        weather_state["points"] = payload.get("points", [])
    except WeatherConnectorError as exc:
        error_message = str(exc)
        logger.error("weather_read.failed error=%s", error_message)
        weather_state["error"] = error_message
    return {"weather": weather_state}
