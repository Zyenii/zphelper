from __future__ import annotations

from enum import StrEnum


class Intent(StrEnum):
    UNKNOWN = "unknown"
    SCHEDULE_SUMMARY = "schedule_summary"
    COMMUTE_ADVICE = "commute_advice"
    WEATHER_SUMMARY = "weather_summary"
    ETA_QUERY = "eta_query"


INTENT_DESCRIPTIONS: dict[Intent, str] = {
    Intent.UNKNOWN: "Unknown or ambiguous request / 不确定或多意图冲突",
    Intent.SCHEDULE_SUMMARY: "Calendar schedule summary or availability / 日程汇总与忙闲查询",
    Intent.COMMUTE_ADVICE: "Commute departure timing and weather travel advice / 出发时间与通勤天气建议",
    Intent.WEATHER_SUMMARY: "Weather query for a requested time range / 指定时间段天气查询",
    Intent.ETA_QUERY: "How long to drive to destination now / 查询去某地需要多久",
}


def all_intent_values() -> list[str]:
    return [item.value for item in Intent]
