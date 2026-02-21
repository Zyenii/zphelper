from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    trace_id: str
    user_message: str
    intent: str
    output: str
    calendar: dict[str, Any]
    schedule: dict[str, Any]
