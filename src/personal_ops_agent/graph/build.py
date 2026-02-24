from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from personal_ops_agent.graph.nodes.final import final_node
from personal_ops_agent.graph.nodes.commute_plan import commute_plan_node
from personal_ops_agent.graph.nodes.router import router_node
from personal_ops_agent.graph.nodes.schedule_read import schedule_read_node
from personal_ops_agent.graph.nodes.schedule_summarize import schedule_summarize_node
from personal_ops_agent.graph.nodes.weather_read import weather_read_node
from personal_ops_agent.graph.nodes.weather_summarize import weather_summarize_node
from personal_ops_agent.graph.state import AgentState


def _route_from_intent(state: AgentState) -> str:
    if state.get("intent") == "eta_query":
        return "eta_path"
    if state.get("intent") == "commute_advice":
        return "commute_path"
    if state.get("intent") == "weather_summary":
        return "weather_path"
    if state.get("intent") == "schedule_summary":
        return "schedule_path"
    return "default_path"


@lru_cache
def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("router", router_node)
    graph.add_node("schedule_read", schedule_read_node)
    graph.add_node("schedule_summarize", schedule_summarize_node)
    graph.add_node("weather_read", weather_read_node)
    graph.add_node("weather_summarize", weather_summarize_node)
    graph.add_node("commute_plan", commute_plan_node)
    graph.add_node("final", final_node)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        _route_from_intent,
        {
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
            "eta_path": "commute_plan",
            "commute_path": "commute_plan",
            "weather_path": "weather_summarize",
            "default_path": "final",
        },
    )
    graph.add_edge("weather_summarize", "final")
    graph.add_edge("commute_plan", "final")
    graph.add_edge("schedule_summarize", "final")
    graph.add_edge("final", END)
    return graph.compile()
