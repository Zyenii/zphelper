from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class UserProfileMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_timezone: str | None = None
    home_location: str | None = None
    preferred_transport_mode: str | None = None
    default_calendar_id: str | None = None


class PreferenceMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rain_alert_threshold: float | None = None
    cold_alert_celsius: float | None = None
    extra_buffer_minutes: int | None = None


class BehavioralNotesMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meeting_prep: list[str] = Field(default_factory=list)
    interview_prep: list[str] = Field(default_factory=list)
    presentation_prep: list[str] = Field(default_factory=list)


class PersonalMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_profile: UserProfileMemory = Field(default_factory=UserProfileMemory)
    preferences: PreferenceMemory = Field(default_factory=PreferenceMemory)
    place_aliases: dict[str, str] = Field(default_factory=dict)
    behavioral_notes: BehavioralNotesMemory = Field(default_factory=BehavioralNotesMemory)


DEFAULT_MEMORY = PersonalMemory()
