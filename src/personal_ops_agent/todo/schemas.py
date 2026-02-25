from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TodoDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    due: str | None = None
    priority: int = 2
    labels: list[str] = Field(default_factory=list)
    project_id: str | None = None
    notes: str | None = None
    source_event_id: str | None = None
    confidence: float
    rationale: str

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("title cannot be empty")
        return trimmed

    @field_validator("due")
    @classmethod
    def validate_due(cls, value: str | None) -> str | None:
        if value is None:
            return None
        raw = value.strip()
        if not raw:
            return None
        try:
            if "T" in raw:
                datetime.fromisoformat(raw.replace("Z", "+00:00"))
            else:
                date.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError("due must be ISO8601 date or datetime") from exc
        return raw

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: int) -> int:
        if value < 1 or value > 4:
            raise ValueError("priority must be between 1 and 4")
        return value

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        if not (0.0 <= value <= 1.0):
            raise ValueError("confidence must be in [0,1]")
        return value


class TodoCreateResult(BaseModel):
    task_id: str
    url: str | None = None
    normalized_due: str | None = None
    priority: int


class TodoTaskSummary(BaseModel):
    task_id: str
    title: str
    due: str | None = None
    priority: int
    url: str | None = None


TODO_JSON_SCHEMA: dict[str, Any] = TodoDraft.model_json_schema()
