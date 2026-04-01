from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Request

from personal_ops_agent.api.schemas import ChatRequest, ChatResponse, HealthResponse
from personal_ops_agent.core.logging import log_event
from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.core.telemetry import get_runtime_stats
from personal_ops_agent.graph.build import build_graph
from personal_ops_agent.session.store import clear_continuation, load_continuation, save_continuation

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    trace_id = getattr(request.state, "trace_id", str(uuid4()))
    settings = get_settings()
    session_id = payload.session_id
    state = {"trace_id": trace_id, "user_message": payload.message, "session_id": session_id}
    result = build_graph().invoke(state)
    plan = result.get("plan", {})
    status = plan.get("status") if isinstance(plan, dict) else None

    if status == "needs_clarification":
        existing = load_continuation(session_id)
        turn_count = 1 if not existing else int(existing.get("turn_count", 0)) + 1
        if turn_count >= settings.MAX_CLARIFICATION_TURNS:
            clear_continuation(session_id)
            result["output"] = "当前信息仍不足以完成这个任务，请重新完整描述你的需求。"
        else:
            original_user_request = payload.message
            if existing and isinstance(existing.get("original_user_request"), str):
                original_user_request = existing["original_user_request"]
            merged_known_slots = {}
            if existing and isinstance(existing.get("known_slots"), dict):
                merged_known_slots.update(existing["known_slots"])
            if isinstance(plan.get("known_slots"), dict):
                merged_known_slots.update(plan["known_slots"])
            save_continuation(
                session_id,
                {
                    "active": True,
                    "original_user_request": original_user_request,
                    "intent": plan.get("intent", "unknown"),
                    "known_slots": merged_known_slots,
                    "missing_slots": plan.get("missing_slots", []),
                    "last_clarification_question": plan.get("clarification_question"),
                    "turn_count": turn_count,
                },
            )
            result["output"] = plan.get("clarification_question", "请补充更多信息。")
    elif status in {"ready", "cannot_complete"}:
        clear_continuation(session_id)

    intent = result.get("intent", "unknown")
    output = result.get("output", "")

    log_event(logger, "chat.completed", intent=intent)

    state_snapshot = {"intent": intent, "output": output}
    if "calendar" in result:
        state_snapshot["calendar"] = result["calendar"]
    if "calendar_write" in result:
        state_snapshot["calendar_write"] = result["calendar_write"]
    if "schedule" in result:
        state_snapshot["schedule"] = result["schedule"]
    if "weather" in result:
        state_snapshot["weather"] = result["weather"]
    if "commute" in result:
        state_snapshot["commute"] = result["commute"]
    if "todo" in result:
        state_snapshot["todo"] = result["todo"]
    if "checklist" in result:
        state_snapshot["checklist"] = result["checklist"]
    if "memory" in result:
        state_snapshot["memory"] = result["memory"]
    if "plan" in result:
        state_snapshot["plan"] = result["plan"]
    if "plan_confidence" in result:
        state_snapshot["plan_confidence"] = result["plan_confidence"]
    if "plan_reason" in result:
        state_snapshot["plan_reason"] = result["plan_reason"]
    if "plan_used" in result:
        state_snapshot["plan_used"] = result["plan_used"]
    if "eval" in result:
        state_snapshot["eval"] = result["eval"]
    state_snapshot["session_id"] = session_id
    state_snapshot["eval"] = {**state_snapshot.get("eval", {}), "runtime": get_runtime_stats()}

    return ChatResponse(
        trace_id=trace_id,
        intent=intent,
        output=output,
        state=state_snapshot,
    )
