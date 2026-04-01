from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    trace_id: str
    session_id: str
    user_message: str
    intent: str
    output: str
    calendar: dict[str, Any]
    calendar_write: dict[str, Any]
    schedule: dict[str, Any]
    weather: dict[str, Any]
    commute: dict[str, Any]
    todo: dict[str, Any]
    checklist: dict[str, Any]
    memory: dict[str, Any]
    eval: dict[str, Any]
    plan: dict[str, Any]
    plan_confidence: float
    plan_reason: str
    plan_used: bool
    action_tool: str
    action_args: dict[str, Any]
    route_confidence: float
    route_reason: str
