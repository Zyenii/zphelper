from __future__ import annotations

from dataclasses import dataclass
import logging

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.router.intent import Intent
from personal_ops_agent.router.llm_router import LLMRouteResult, llm_route

logger = logging.getLogger(__name__)

SCHEDULE_KEYWORDS = {
    "schedule",
    "calendar",
    "agenda",
    "日程",
    "安排",
}

SCHEDULE_TIME_KEYWORDS = {
    "today",
    "tomorrow",
    "this week",
    "next week",
    "weekend",
    "今天",
    "明天",
    "后天",
    "本周",
    "这周",
    "下周",
    "周末",
}

COMMUTE_KEYWORDS = {
    "commute",
    "leave",
    "departure",
    "umbrella",
    "traffic",
    "出门",
    "出发",
    "通勤",
    "带伞",
    "几点出发",
}

WEATHER_KEYWORDS = {
    "weather",
    "forecast",
    "temperature",
    "rain",
    "wind",
    "天气",
    "温度",
    "下雨",
    "降雨",
    "风",
}

ETA_QUERY_KEYWORDS = {
    "how long to",
    "how long does it take",
    "多久",
    "多长时间",
    "要多久",
}

TODO_KEYWORDS = {
    "todo",
    "task",
    "remind me",
    "add task",
    "add todo",
    "待办",
    "任务",
    "提醒我",
    "记得",
}

CHECKLIST_KEYWORDS = {
    "what should i bring",
    "leaving checklist",
    "checklist",
    "带什么",
    "出门清单",
    "下个日程总结",
}

CALENDAR_CREATE_KEYWORDS = {
    "create event",
    "add event",
    "add to calendar",
    "schedule a meeting",
    "创建日程",
    "添加日程",
    "加到日历",
    "安排会议",
}


@dataclass(frozen=True)
class RouteDecision:
    intent: str
    confidence: float
    reason: str


def rule_route(message: str) -> RouteDecision:
    lowered = message.lower()
    if any(keyword in lowered or keyword in message for keyword in CALENDAR_CREATE_KEYWORDS):
        return RouteDecision(intent=Intent.CALENDAR_CREATE.value, confidence=1.0, reason="rule_match_calendar_create")
    if any(keyword in lowered or keyword in message for keyword in TODO_KEYWORDS):
        return RouteDecision(intent=Intent.TODO_CREATE.value, confidence=1.0, reason="rule_match_todo")
    if any(keyword in lowered or keyword in message for keyword in CHECKLIST_KEYWORDS):
        return RouteDecision(intent=Intent.LEAVING_CHECKLIST.value, confidence=1.0, reason="rule_match_checklist")
    if any(keyword in lowered or keyword in message for keyword in ETA_QUERY_KEYWORDS) and (
        "to " in lowered or "去" in message or "到" in message
    ):
        return RouteDecision(intent=Intent.ETA_QUERY.value, confidence=1.0, reason="rule_match_eta_query")
    if any(keyword in lowered or keyword in message for keyword in COMMUTE_KEYWORDS):
        return RouteDecision(intent=Intent.COMMUTE_ADVICE.value, confidence=1.0, reason="rule_match_commute")
    if any(keyword in lowered or keyword in message for keyword in WEATHER_KEYWORDS):
        return RouteDecision(intent=Intent.WEATHER_SUMMARY.value, confidence=1.0, reason="rule_match_weather")
    has_schedule_domain = any(keyword in lowered or keyword in message for keyword in SCHEDULE_KEYWORDS)
    has_schedule_time = any(keyword in lowered or keyword in message for keyword in SCHEDULE_TIME_KEYWORDS)
    if has_schedule_domain and has_schedule_time:
        return RouteDecision(intent=Intent.SCHEDULE_SUMMARY.value, confidence=1.0, reason="rule_match_schedule")
    return RouteDecision(intent=Intent.UNKNOWN.value, confidence=0.0, reason="rule_unknown")


def should_use_llm_router() -> bool:
    settings = get_settings()
    return bool(settings.LLM_ROUTER and settings.OPENAI_API_KEY)


def dispatch_intent(message: str) -> RouteDecision:
    rule_decision = rule_route(message)
    logger.info(
        "router.rule_result intent=%s confidence=%.2f reason=%s",
        rule_decision.intent,
        rule_decision.confidence,
        rule_decision.reason,
    )
    if rule_decision.intent != Intent.UNKNOWN.value:
        logger.info("router.llm_called=false reason=rule_non_unknown")
        return rule_decision

    if not should_use_llm_router():
        logger.info("router.llm_called=false reason=llm_disabled_or_missing_key")
        return rule_decision

    logger.info("router.llm_called=true")
    llm_decision: LLMRouteResult = llm_route(message)
    logger.info(
        "router.llm_result intent=%s confidence=%.2f reason=%s",
        llm_decision.intent,
        llm_decision.confidence,
        llm_decision.reason,
    )
    return RouteDecision(
        intent=llm_decision.intent,
        confidence=llm_decision.confidence,
        reason=llm_decision.reason,
    )
