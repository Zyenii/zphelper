from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class BufferBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_prep: int
    add_parking: int
    add_weather: int
    add_peak: int
    add_importance: int
    total: int


class CommuteRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: str
    destination: str
    used_calendar_destination: bool
    eta_minutes: int | None = None
    baseline_minutes: int | None = None
    traffic_delay_minutes: int | None = None
    traffic_ratio: float | None = None
    peak: bool | None = None
    eta_source_used: str
    fetched_at_utc: str | None = None
    buffer_minutes: int | None = None
    buffer_breakdown: BufferBreakdown | None = None
    departure_time: str | None = None
    transport_mode: str | None = None
    weather_advice: str | None = None
    explanation: str | None = None
    event_start_time: str | None = None
    event_title: str | None = None
    latest_leave_time: str | None = None
    comfortable_leave_time: str | None = None
    leave_time: str | None = None
    needs_clarification: bool | None = None
    clarification_question: str | None = None
    error: str | None = None
