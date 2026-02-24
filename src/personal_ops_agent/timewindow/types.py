from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, field_validator


class TimeWindow(BaseModel):
    start_utc: datetime
    end_utc: datetime
    tz: str
    granularity: Literal["day", "week", "range"]
    source: Literal["rule", "llm", "default"]
    confidence: float | None = None
    reason: str | None = None

    @field_validator("start_utc", "end_utc")
    @classmethod
    def validate_aware_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone(timezone.utc)
