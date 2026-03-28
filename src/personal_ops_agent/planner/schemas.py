from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from personal_ops_agent.router.intent import all_intent_values

AllowedTool = Literal[
    "schedule_read",
    "schedule_summarize",
    "weather_read",
    "weather_summarize",
    "commute_plan",
    "todo_read",
    "todo_parse",
    "todo_write",
    "checklist_generate",
    "calendar_create",
]


class PlanAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: AllowedTool
    args: dict[str, Any] = Field(default_factory=dict)


class ExecutionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str
    intent: str
    actions: list[PlanAction]
    reason: str
    confidence: float

    @field_validator("intent")
    @classmethod
    def validate_intent(cls, value: str) -> str:
        if value not in all_intent_values():
            raise ValueError("intent must be a supported enum value")
        return value

    @field_validator("actions")
    @classmethod
    def validate_actions(cls, value: list[PlanAction]) -> list[PlanAction]:
        return value

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        if not (0.0 <= value <= 1.0):
            raise ValueError("confidence must be in [0,1]")
        return value
