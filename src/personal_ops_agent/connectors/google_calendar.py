from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from personal_ops_agent.core.settings import get_settings

logger = logging.getLogger(__name__)


class CalendarConnectorError(RuntimeError):
    """Raised when calendar events cannot be fetched or parsed."""


class NormalizedCalendarEvent(BaseModel):
    id: str
    title: str
    start: str
    end: str
    location: str | None = None
    is_all_day: bool = False
    timezone: str = "UTC"


def _parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_mock_events() -> list[NormalizedCalendarEvent]:
    settings = get_settings()
    fixture_path = Path(settings.CALENDAR_FIXTURE_PATH)
    if not fixture_path.is_absolute():
        fixture_path = _repo_root() / fixture_path

    if not fixture_path.exists():
        raise CalendarConnectorError(f"Mock calendar fixture not found: {fixture_path}")

    try:
        with fixture_path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except json.JSONDecodeError as exc:
        raise CalendarConnectorError(f"Invalid mock calendar JSON: {fixture_path}") from exc

    raw_events = payload["events"] if isinstance(payload, dict) else payload
    try:
        return [NormalizedCalendarEvent.model_validate(item) for item in raw_events]
    except Exception as exc:  # noqa: BLE001
        raise CalendarConnectorError("Mock calendar fixture contains invalid events.") from exc


def _read_google_events_oauth(window_start: datetime, window_end: datetime) -> list[NormalizedCalendarEvent]:
    settings = get_settings()
    client_secret_path = settings.GOOGLE_OAUTH_CLIENT_SECRET_JSON
    token_path = settings.GOOGLE_OAUTH_TOKEN_JSON
    if not client_secret_path or not token_path:
        raise CalendarConnectorError(
            "OAuth mode requires GOOGLE_OAUTH_CLIENT_SECRET_JSON and GOOGLE_OAUTH_TOKEN_JSON."
        )

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise CalendarConnectorError(
            "OAuth mode requires google-api-python-client, google-auth, and google-auth-oauthlib."
        ) from exc

    scopes = ["https://www.googleapis.com/auth/calendar.readonly"]
    token_file = Path(token_path)
    client_secret_file = Path(client_secret_path)
    if not client_secret_file.exists():
        raise CalendarConnectorError(f"OAuth client secret file not found: {client_secret_file}")

    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), scopes)
            creds = flow.run_local_server(port=0)
        token_file.write_text(creds.to_json(), encoding="utf-8")

    service = build("calendar", "v3", credentials=creds)
    response = (
        service.events()
        .list(
            calendarId=settings.GOOGLE_CALENDAR_ID,
            timeMin=window_start.isoformat(),
            timeMax=window_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    result: list[NormalizedCalendarEvent] = []
    for item in response.get("items", []):
        start_obj = item.get("start", {})
        end_obj = item.get("end", {})
        start_val = start_obj.get("dateTime") or start_obj.get("date")
        end_val = end_obj.get("dateTime") or end_obj.get("date")
        if not start_val or not end_val:
            continue
        timezone_name = start_obj.get("timeZone") or "UTC"
        is_all_day = "date" in start_obj and "dateTime" not in start_obj
        result.append(
            NormalizedCalendarEvent(
                id=item.get("id", ""),
                title=item.get("summary") or "Untitled",
                start=_parse_iso(start_val).isoformat(),
                end=_parse_iso(end_val).isoformat(),
                location=item.get("location"),
                is_all_day=is_all_day,
                timezone=timezone_name,
            )
        )
    return result


def get_calendar_events(window_start: datetime, window_end: datetime) -> list[dict[str, Any]]:
    settings = get_settings()
    use_mock = settings.MOCK_CALENDAR or settings.GOOGLE_CALENDAR_MODE == "mock"
    try:
        if use_mock:
            events = _load_mock_events()
        else:
            events = _read_google_events_oauth(window_start, window_end)

        filtered = [
            event
            for event in events
            if _parse_iso(event.start) < window_end and _parse_iso(event.end) > window_start
        ]

        # Keep M2 usable without date-specific fixture maintenance.
        if use_mock and not filtered:
            logger.info("calendar.mock_window_empty returning_all_fixture_events")
            filtered = events

        logger.info("calendar.events_loaded count=%s mode=%s", len(filtered), "mock" if use_mock else "oauth")
        return [event.model_dump() for event in filtered]
    except CalendarConnectorError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise CalendarConnectorError(f"Failed to fetch calendar events: {exc}") from exc
