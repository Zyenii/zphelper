from __future__ import annotations

from collections.abc import Callable

from personal_ops_agent.graph.state import AgentState
from personal_ops_agent.graph.nodes.calendar_create import calendar_create_node
from personal_ops_agent.graph.nodes.checklist_generate import checklist_generate_node
from personal_ops_agent.graph.nodes.commute_plan import commute_plan_node
from personal_ops_agent.graph.nodes.schedule_read import schedule_read_node
from personal_ops_agent.graph.nodes.schedule_summarize import schedule_summarize_node
from personal_ops_agent.graph.nodes.todo_read import todo_read_node
from personal_ops_agent.graph.nodes.todo_parse import todo_parse_node
from personal_ops_agent.graph.nodes.todo_write import todo_write_node
from personal_ops_agent.graph.nodes.weather_read import weather_read_node
from personal_ops_agent.graph.nodes.weather_summarize import weather_summarize_node

NodeFn = Callable[[AgentState], AgentState]

ACTION_MAP: dict[str, NodeFn] = {
    "schedule_read": schedule_read_node,
    "schedule_summarize": schedule_summarize_node,
    "weather_read": weather_read_node,
    "weather_summarize": weather_summarize_node,
    "commute_plan": commute_plan_node,
    "todo_read": todo_read_node,
    "todo_parse": todo_parse_node,
    "todo_write": todo_write_node,
    "checklist_generate": checklist_generate_node,
    "calendar_create": calendar_create_node,
}


def execute_plan(state: AgentState) -> AgentState:
    plan = state.get("plan", {})
    actions = plan.get("actions", []) if isinstance(plan, dict) else []
    current: AgentState = dict(state)
    executed: list[str] = []

    for action in actions:
        if not isinstance(action, dict):
            continue
        tool = action.get("tool")
        if not isinstance(tool, str) or tool not in ACTION_MAP:
            continue
        args = action.get("args", {})
        if not isinstance(args, dict):
            args = {}
        current["action_tool"] = tool
        current["action_args"] = args
        node = ACTION_MAP[tool]
        patch = node(current)
        current.update(patch)
        executed.append(tool)

    current["plan_used"] = True
    current.pop("action_tool", None)
    current.pop("action_args", None)
    current["eval"] = {
        **current.get("eval", {}),
        "planner": {
            "executed_actions": executed,
            "planned_actions": [item.get("tool") for item in actions if isinstance(item, dict)],
        },
    }
    return current
