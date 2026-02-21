from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from personal_ops_agent.graph.nodes.final import final_node
from personal_ops_agent.graph.nodes.router import router_node
from personal_ops_agent.graph.nodes.schedule_read import schedule_read_node
from personal_ops_agent.graph.nodes.schedule_summarize import schedule_summarize_node
from personal_ops_agent.graph.state import AgentState


def _route_from_intent(state: AgentState) -> str:
    if state.get("intent") == "schedule_summary":
        return "schedule_path"
    return "default_path"


@lru_cache
def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("router", router_node)
    graph.add_node("schedule_read", schedule_read_node)
    graph.add_node("schedule_summarize", schedule_summarize_node)
    graph.add_node("final", final_node)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        _route_from_intent,
        {"schedule_path": "schedule_read", "default_path": "final"},
    )
    graph.add_edge("schedule_read", "schedule_summarize")
    graph.add_edge("schedule_summarize", "final")
    graph.add_edge("final", END)
    return graph.compile()
