from __future__ import annotations

from dataclasses import replace
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from personal_ops_agent.commute.buffer import compute_buffer_minutes
from personal_ops_agent.commute.context import resolve_trip_context
from personal_ops_agent.commute.schemas import CommuteRecommendation
from personal_ops_agent.connectors.eta import EtaConnectorError, get_eta
from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.graph.state import AgentState

logger = logging.getLogger(__name__)


def _parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _resolve_now() -> datetime:
    settings = get_settings()
    if settings.COMMUTE_NOW_ISO:
        return _parse_iso(settings.COMMUTE_NOW_ISO)
    return datetime.now(timezone.utc)


def _local_time_text(dt: datetime, timezone_name: str) -> str:
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        tz = timezone.utc
    return dt.astimezone(tz).strftime("%m-%d %H:%M")


def _transport_mode_label(mode: str | None) -> str:
    normalized = (mode or "").strip().lower()
    if normalized in {"driving", "drive", "car"}:
        return "开车"
    if normalized in {"transit", "public_transit"}:
        return "乘公共交通"
    if normalized in {"walking", "walk"}:
        return "步行"
    if normalized == "taxi":
        return "打车"
    return "前往"


def _derive_transport_mode(weather_state: dict, eta_state: dict) -> tuple[str, str]:
    points = weather_state.get("points", [])
    rain_max_pct = max((int(point.get("rain_probability", 0)) for point in points), default=0)
    if rain_max_pct >= 40:
        return "taxi", "有降雨风险，建议优先打车，减少淋雨和等车不确定性。"
    if bool(eta_state.get("peak", False)):
        return "transit", "当前路况偏拥堵，公共交通通常更稳定。"
    return "walk", "天气与路况都较平稳，短途可步行或按常规方式出发。"


def _override_trip_from_action_args(trip, action_args: dict, now_utc: datetime):
    if not action_args:
        return trip

    destination = action_args.get("destination")
    departure_time = action_args.get("departure_time")
    origin = action_args.get("origin")

    updated = trip
    if isinstance(destination, str) and destination.strip():
        updated = replace(updated, destination_text=destination.strip(), used_calendar_destination=False)
    if isinstance(origin, str) and origin.strip():
        updated = replace(updated, origin_text=origin.strip())
    if isinstance(departure_time, str):
        if departure_time == "now":
            updated = replace(updated, departure_time=now_utc)
        else:
            try:
                updated = replace(updated, departure_time=_parse_iso(departure_time))
            except ValueError:
                pass
    return updated


def _select_transport_mode(
    *,
    intent: str,
    requested_mode: str | None,
    weather_state: dict,
    eta_state: dict,
) -> tuple[str, str]:
    normalized = (requested_mode or "").strip().lower()
    if normalized in {"driving", "drive", "car"}:
        return "driving", "按驾车 ETA 执行，本次结果保留为 driving，不自动改写成其他交通方式。"
    if normalized in {"transit", "public_transit"}:
        return "transit", "planner 请求了 transit 模式，但当前 ETA 仍是 driving-first 估算，请谨慎解读。"
    if normalized in {"walking", "walk"}:
        return "walking", "planner 请求了 walking 模式，但当前 ETA 仍是 driving-first 估算，请谨慎解读。"
    if intent == "eta_query":
        return "driving", "eta_query 默认采用 driving-first 语义；若需公交/步行，请在请求里显式说明。"
    return _derive_transport_mode(weather_state=weather_state, eta_state=eta_state)


def _reconcile_eta_query_mode(
    *,
    requested_mode: str | None,
    selected_mode: str,
    weather_advice: str,
) -> tuple[str, str]:
    normalized = (requested_mode or "").strip().lower()
    if normalized in {"transit", "public_transit"}:
        return (
            "driving",
            "当前 ETA connector 仅支持 driving-first 估算；你问的是公共交通，我先返回驾车 ETA 供参考。",
        )
    if normalized in {"walking", "walk"}:
        return (
            "driving",
            "当前 ETA connector 仅支持 driving-first 估算；你问的是步行，我先返回驾车 ETA 供参考。",
        )
    if normalized == "taxi":
        return (
            "driving",
            "当前 ETA connector 仅支持 driving-first 估算；打车与驾车路况接近，这里返回驾车 ETA 供参考。",
        )
    return selected_mode, weather_advice


def commute_plan_node(state: AgentState) -> AgentState:
    settings = get_settings()
    intent = state.get("intent", "commute_advice")
    message = state.get("user_message", "")
    calendar_state = state.get("calendar", {})
    weather_state = state.get("weather", {})
    memory_state = state.get("memory", {})
    action_args = state.get("action_args", {}) if state.get("action_tool") == "commute_plan" else {}
    now_utc = _resolve_now()

    trip = resolve_trip_context(
        message=message,
        intent=intent,
        calendar_state=calendar_state,
        now_utc=now_utc,
        timezone_name=settings.DEFAULT_TIMEZONE,
        default_origin=settings.DEFAULT_ORIGIN,
        memory_state=memory_state,
    )
    if isinstance(action_args, dict):
        trip = _override_trip_from_action_args(trip, action_args, now_utc)

    if trip.needs_clarification:
        clarification = trip.clarification_question or "Where are you going?"
        recommendation = CommuteRecommendation(
            origin=trip.origin_text,
            destination=trip.destination_text,
            used_calendar_destination=False,
            eta_source_used="clarification",
            needs_clarification=True,
            clarification_question=clarification,
        ).model_dump(exclude_none=True)
        return {
            "commute": {"recommendation": recommendation},
            "output": clarification,
        }

    try:
        eta_state = get_eta(
            depart_time=trip.departure_time,
            origin_text=trip.origin_text,
            destination_text=trip.destination_text,
        )
    except EtaConnectorError as exc:
        logger.error("commute_eta.failed error=%s", exc)
        error_text = f"ETA service unavailable: {exc}"
        recommendation = CommuteRecommendation(
            origin=trip.origin_text,
            destination=trip.destination_text,
            used_calendar_destination=trip.used_calendar_destination,
            eta_source_used="error",
            error=error_text,
        ).model_dump(exclude_none=True)
        return {
            "commute": {"recommendation": recommendation},
            "output": f"暂时无法获取实时通勤时间。{error_text}",
        }
    logger.info(
        "commute.context origin=%s destination=%s calendar_destination=%s eta_source=%s",
        trip.origin_text,
        trip.destination_text,
        trip.used_calendar_destination,
        eta_state.get("source", "error"),
    )

    eta_minutes = int(eta_state.get("eta_minutes", settings.ETA_BASE_MINUTES))
    buffer_minutes, breakdown = compute_buffer_minutes(weather_state=weather_state, eta_state=eta_state)
    extra_buffer = (memory_state.get("preferences", {}) or {}).get("extra_buffer_minutes")
    if isinstance(extra_buffer, int) and extra_buffer > 0:
        buffer_minutes = max(5, min(25, buffer_minutes + extra_buffer))
        breakdown["memory_extra_buffer"] = extra_buffer
        breakdown["total"] = buffer_minutes
    requested_mode = action_args.get("transport_mode") if isinstance(action_args, dict) else None
    transport_mode, weather_advice = _select_transport_mode(
        intent=intent,
        requested_mode=requested_mode,
        weather_state=weather_state,
        eta_state=eta_state,
    )
    if intent == "eta_query":
        transport_mode, weather_advice = _reconcile_eta_query_mode(
            requested_mode=requested_mode,
            selected_mode=transport_mode,
            weather_advice=weather_advice,
        )
    explanation = (
        f"ETA {eta_minutes} 分钟，缓冲 {buffer_minutes} 分钟（准备{breakdown['base_prep']}+停车{breakdown['add_parking']}"
        f"+天气{breakdown['add_weather']}+高峰{breakdown['add_peak']}）。"
    )

    recommendation_payload: dict[str, object] = {
        "origin": trip.origin_text,
        "destination": trip.destination_text,
        "used_calendar_destination": trip.used_calendar_destination,
        "eta_minutes": eta_minutes,
        "baseline_minutes": eta_state.get("baseline_minutes"),
        "traffic_delay_minutes": eta_state.get("traffic_delay_minutes"),
        "traffic_ratio": eta_state.get("traffic_ratio"),
        "peak": bool(eta_state.get("peak", False)),
        "eta_source_used": eta_state.get("source", "error"),
        "fetched_at_utc": eta_state.get("fetched_at_utc"),
        "buffer_minutes": buffer_minutes,
        "buffer_breakdown": breakdown,
        "departure_time": trip.departure_time.isoformat(),
        "transport_mode": transport_mode,
        "weather_advice": weather_advice,
        "explanation": explanation,
    }

    if intent == "eta_query" or not trip.event_start_time:
        delay = eta_state.get("traffic_delay_minutes")
        delay_text = f"，交通额外延迟约 {delay} 分钟" if isinstance(delay, int) else ""
        mode_label = _transport_mode_label(transport_mode)
        advisory_text = f"{weather_advice}" if weather_advice else ""
        output = (
            f"从{trip.origin_text}{mode_label}到{trip.destination_text}，当前预计约 {eta_minutes} 分钟{delay_text}。"
            f"数据来源：{eta_state.get('source', 'error')}。"
        )
        if advisory_text and "driving-first" in advisory_text:
            output = f"{output}{advisory_text}"
        recommendation = CommuteRecommendation.model_validate(recommendation_payload).model_dump(exclude_none=True)
        return {"commute": {"recommendation": recommendation}, "output": output}

    latest_leave = trip.event_start_time - timedelta(minutes=eta_minutes + buffer_minutes)
    comfortable_leave = latest_leave - timedelta(minutes=5)
    recommendation_payload["event_start_time"] = trip.event_start_time.isoformat()
    recommendation_payload["event_title"] = trip.event_title
    recommendation_payload["latest_leave_time"] = latest_leave.isoformat()
    recommendation_payload["comfortable_leave_time"] = comfortable_leave.isoformat()
    recommendation_payload["leave_time"] = latest_leave.isoformat()

    output = (
        f"你下一个日程{('“' + trip.event_title + '”') if trip.event_title else ''}在"
        f"{_local_time_text(trip.event_start_time, settings.DEFAULT_TIMEZONE)}开始，目的地是{trip.destination_text}。"
        f"从{trip.origin_text}出发，当前路况预计 {eta_minutes} 分钟；"
        f"缓冲 {buffer_minutes} 分钟（准备{breakdown['base_prep']}+停车{breakdown['add_parking']}"
        f"+天气{breakdown['add_weather']}+高峰{breakdown['add_peak']}）。"
        f"最晚建议 { _local_time_text(latest_leave, settings.DEFAULT_TIMEZONE)} 出门，"
        f"更稳妥可在 { _local_time_text(comfortable_leave, settings.DEFAULT_TIMEZONE)} 出门。"
        f"ETA来源：{eta_state.get('source', 'error')}。"
    )
    recommendation = CommuteRecommendation.model_validate(recommendation_payload).model_dump(exclude_none=True)
    return {"commute": {"recommendation": recommendation}, "output": output}
