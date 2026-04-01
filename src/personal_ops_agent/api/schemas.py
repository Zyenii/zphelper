from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, description="User input message.")
    session_id: str = Field(default="default", min_length=1, description="Session identifier for short-term continuation.")


class ChatResponse(BaseModel):
    trace_id: str
    intent: str
    output: str
    state: dict[str, Any]
