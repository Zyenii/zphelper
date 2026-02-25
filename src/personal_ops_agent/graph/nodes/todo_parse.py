from __future__ import annotations

from personal_ops_agent.graph.state import AgentState
from personal_ops_agent.todo.parser import parse_todo_with_retries


def _build_context(state: AgentState) -> dict:
    calendar_state = state.get("calendar", {})
    events = calendar_state.get("events", [])
    if events:
        next_event = sorted(events, key=lambda item: item.get("start", ""))[0]
        return {"next_event": next_event}
    return {}


def todo_parse_node(state: AgentState) -> AgentState:
    message = state.get("user_message", "")
    draft = parse_todo_with_retries(raw_text=message, trace_id=state.get("trace_id"), context=_build_context(state))
    return {"todo": {"draft": draft.model_dump()}}
