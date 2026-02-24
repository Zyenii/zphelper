from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Request

from personal_ops_agent.api.schemas import ChatRequest, ChatResponse, HealthResponse
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

    logger.info("chat.completed intent=%s", intent)

    state_snapshot = {"intent": intent, "output": output}
    if "calendar" in result:
        state_snapshot["calendar"] = result["calendar"]
    if "schedule" in result:
        state_snapshot["schedule"] = result["schedule"]
    if "weather" in result:
        state_snapshot["weather"] = result["weather"]
    if "commute" in result:
        state_snapshot["commute"] = result["commute"]

    return ChatResponse(
        trace_id=trace_id,
        intent=intent,
        output=output,
        state=state_snapshot,
    )
