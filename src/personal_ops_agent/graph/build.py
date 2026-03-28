from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from personal_ops_agent.graph.nodes.final import final_node
from personal_ops_agent.graph.nodes.calendar_create import calendar_create_node
from personal_ops_agent.graph.nodes.checklist_generate import checklist_generate_node
from personal_ops_agent.graph.nodes.commute_plan import commute_plan_node
from personal_ops_agent.graph.nodes.planner import planner_node
from personal_ops_agent.graph.nodes.router import router_node
from personal_ops_agent.graph.nodes.schedule_read import schedule_read_node
from personal_ops_agent.graph.nodes.schedule_summarize import schedule_summarize_node
from personal_ops_agent.graph.nodes.todo_read import todo_read_node
from personal_ops_agent.graph.nodes.todo_parse import todo_parse_node
from personal_ops_agent.graph.nodes.todo_write import todo_write_node
from personal_ops_agent.graph.nodes.weather_read import weather_read_node
from personal_ops_agent.graph.nodes.weather_summarize import weather_summarize_node
from personal_ops_agent.graph.state import AgentState
from personal_ops_agent.planner.executor import execute_plan


def _route_from_intent(state: AgentState) -> str:
    if state.get("intent") == "calendar_create":
        return "calendar_create_path"
    if state.get("intent") == "todo_create":
        return "todo_path"
    if state.get("intent") == "todo_list":
        return "todo_list_path"
    if state.get("intent") == "leaving_checklist":
        return "checklist_path"
    if state.get("intent") == "eta_query":
        return "eta_path"
    if state.get("intent") == "commute_advice":
        return "commute_path"
    if state.get("intent") == "weather_summary":
        return "weather_path"
    if state.get("intent") == "schedule_summary":
        return "schedule_path"
    return "default_path"


def _route_from_planner(state: AgentState) -> str:
    if state.get("plan_used") and state.get("plan"):
        return "planner_path"
    return "router_path"


@lru_cache
def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("planner", planner_node)
    graph.add_node("plan_executor", execute_plan)
    graph.add_node("router", router_node)
    graph.add_node("calendar_create", calendar_create_node)
    graph.add_node("schedule_read", schedule_read_node)
    graph.add_node("schedule_summarize", schedule_summarize_node)
    graph.add_node("weather_read", weather_read_node)
    graph.add_node("weather_summarize", weather_summarize_node)
    graph.add_node("commute_plan", commute_plan_node)
    graph.add_node("todo_read", todo_read_node)
    graph.add_node("todo_parse", todo_parse_node)
    graph.add_node("todo_write", todo_write_node)
    graph.add_node("checklist_generate", checklist_generate_node)
    graph.add_node("final", final_node)

    graph.add_edge(START, "planner")
    graph.add_conditional_edges(
        "planner",
        _route_from_planner,
        {
            "planner_path": "plan_executor",
            "router_path": "router",
        },
    )
    graph.add_edge("plan_executor", "final")
    graph.add_conditional_edges(
        "router",
        _route_from_intent,
        {
            "calendar_create_path": "calendar_create",
            "todo_path": "schedule_read",
            "todo_list_path": "todo_read",
            "checklist_path": "schedule_read",
            "eta_path": "commute_plan",
            "commute_path": "schedule_read",
            "schedule_path": "schedule_read",
            "weather_path": "weather_read",
            "default_path": "final",
        },
    )
    graph.add_conditional_edges(
        "schedule_read",
        _route_from_intent,
        {
            "checklist_path": "weather_read",
            "todo_path": "todo_parse",
            "todo_list_path": "final",
            "calendar_create_path": "final",
            "eta_path": "commute_plan",
            "commute_path": "weather_read",
            "schedule_path": "schedule_summarize",
            "weather_path": "weather_read",
            "default_path": "final",
        },
    )
    graph.add_conditional_edges(
        "weather_read",
        _route_from_intent,
        {
            "checklist_path": "commute_plan",
            "todo_path": "final",
            "todo_list_path": "final",
            "calendar_create_path": "final",
            "eta_path": "commute_plan",
            "commute_path": "commute_plan",
            "weather_path": "weather_summarize",
            "default_path": "final",
        },
    )
    graph.add_conditional_edges(
        "commute_plan",
        _route_from_intent,
        {
            "checklist_path": "checklist_generate",
            "default_path": "final",
            "calendar_create_path": "final",
            "eta_path": "final",
            "commute_path": "final",
            "schedule_path": "final",
            "weather_path": "final",
            "todo_path": "final",
        },
    )
    graph.add_edge("calendar_create", "final")
    graph.add_edge("todo_read", "final")
    graph.add_edge("todo_parse", "todo_write")
    graph.add_edge("todo_write", "final")
    graph.add_edge("checklist_generate", "final")
    graph.add_edge("weather_summarize", "final")
    graph.add_edge("schedule_summarize", "final")
    graph.add_edge("final", END)
    return graph.compile()
