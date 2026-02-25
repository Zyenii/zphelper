from __future__ import annotations

from personal_ops_agent.checklist.generator import generate_checklist
from personal_ops_agent.eval.metrics import get_regression_snapshot
from personal_ops_agent.graph.state import AgentState


def checklist_generate_node(state: AgentState) -> AgentState:
    checklist = generate_checklist(
        trace_id=state.get("trace_id"),
        calendar_state=state.get("calendar", {}),
        weather_state=state.get("weather", {}),
        commute_state=state.get("commute", {}),
    )
    return {
        "checklist": checklist.model_dump(),
        "output": checklist.summary,
        "eval": {"todo_regression": get_regression_snapshot()},
    }
