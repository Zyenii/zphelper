from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Request

from personal_ops_agent.api.schemas import ChatRequest, ChatResponse, HealthResponse
from personal_ops_agent.core.logging import log_event
from personal_ops_agent.core.telemetry import get_runtime_stats
from personal_ops_agent.graph.build import build_graph

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    trace_id = getattr(request.state, "trace_id", str(uuid4()))
    state = {"trace_id": trace_id, "user_message": payload.message}
    result = build_graph().invoke(state)

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
    state_snapshot["eval"] = {**state_snapshot.get("eval", {}), "runtime": get_runtime_stats()}

    return ChatResponse(
        trace_id=trace_id,
        intent=intent,
        output=output,
        state=state_snapshot,
    )
