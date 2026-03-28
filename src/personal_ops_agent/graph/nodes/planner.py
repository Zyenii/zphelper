from __future__ import annotations

from datetime import datetime, timezone

from personal_ops_agent.graph.state import AgentState
from personal_ops_agent.memory.context import build_planner_context, build_planner_memory_context
from personal_ops_agent.memory.store import load_memory
from personal_ops_agent.planner.planner import make_plan


def planner_node(state: AgentState) -> AgentState:
    message = state.get("user_message", "")
    memory = load_memory()
    planner_context = build_planner_context(
        user_message=message,
        memory=memory,
        now_utc=datetime.now(timezone.utc),
    )
    plan = make_plan(message, context=planner_context)
    if plan is None:
        return {"plan_used": False, "memory": build_planner_memory_context(memory)}
    return {
        "plan": plan.model_dump(),
        "intent": plan.intent,
        "plan_confidence": plan.confidence,
        "plan_reason": plan.reason,
        "plan_used": True,
        "memory": build_planner_memory_context(memory),
    }
