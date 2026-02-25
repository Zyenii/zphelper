from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LeavingChecklist(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    items: list[str] = Field(min_length=1, max_length=12)
    reasons: list[str] = Field(min_length=1, max_length=12)
    confidence: float

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("summary cannot be empty")
        return text

    @field_validator("items")
    @classmethod
    def validate_items(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("items cannot contain empty strings")
        return value

    @field_validator("reasons")
    @classmethod
    def validate_reasons(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("reasons cannot contain empty strings")
        return value

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        if not (0.0 <= value <= 1.0):
            raise ValueError("confidence must be in [0,1]")
        return value

    def validate_alignment(self) -> None:
        if len(self.items) != len(self.reasons):
            raise ValueError("items and reasons length must match")
