from __future__ import annotations

from datetime import datetime, timezone

from personal_ops_agent.graph.state import AgentState
from personal_ops_agent.memory.context import build_planner_context, build_planner_memory_context
from personal_ops_agent.memory.store import load_memory
from personal_ops_agent.planner.planner import make_plan
from personal_ops_agent.session.store import load_continuation


def planner_node(state: AgentState) -> AgentState:
    message = state.get("user_message", "")
    memory = load_memory()
    session_id = state.get("session_id", "default")
    continuation = load_continuation(session_id)
    planner_context = build_planner_context(
        user_message=message,
        memory=memory,
        now_utc=datetime.now(timezone.utc),
        continuation=continuation,
    )
    plan = make_plan(message, context=planner_context)
    if plan is None:
        return {"plan_used": False, "memory": build_planner_memory_context(memory)}
    plan_payload = plan.model_dump()
    if plan.status == "needs_clarification":
        return {
            "plan": plan_payload,
            "intent": plan.intent,
            "plan_confidence": plan.confidence,
            "plan_reason": plan.reason,
            "plan_used": True,
            "output": plan.clarification_question or "请补充更多信息。",
            "memory": build_planner_memory_context(memory),
        }
    if plan.status == "cannot_complete":
        return {
            "plan": plan_payload,
            "intent": plan.intent,
            "plan_confidence": plan.confidence,
            "plan_reason": plan.reason,
            "plan_used": True,
            "output": "当前信息仍不足以完成这个任务，请重新完整描述你的需求。",
            "memory": build_planner_memory_context(memory),
        }
    return {
        "plan": plan_payload,
        "intent": plan.intent,
        "plan_confidence": plan.confidence,
        "plan_reason": plan.reason,
        "plan_used": True,
        "memory": build_planner_memory_context(memory),
    }
