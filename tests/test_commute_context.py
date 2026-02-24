from datetime import datetime, timezone

from personal_ops_agent.commute.context import resolve_trip_context


def _calendar_state() -> dict:
    return {
        "events": [
            {
                "id": "evt-1",
                "title": "Client Meeting",
                "start": "2026-03-01T15:00:00+00:00",
                "end": "2026-03-01T16:00:00+00:00",
                "location": "Downtown Office",
            }
        ]
    }


def test_destination_from_user_text() -> None:
    context = resolve_trip_context(
        message="我几点出发去机场",
        intent="commute_advice",
        calendar_state=_calendar_state(),
        now_utc=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
        timezone_name="UTC",
        default_origin="Home",
    )
    assert context.destination_text == "机场"
    assert context.used_calendar_destination is False


def test_destination_from_calendar_location() -> None:
    context = resolve_trip_context(
        message="我几点出门比较稳",
        intent="commute_advice",
        calendar_state=_calendar_state(),
        now_utc=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
        timezone_name="UTC",
        default_origin="Home",
    )
    assert context.destination_text == "Downtown Office"
    assert context.used_calendar_destination is True


def test_missing_destination_needs_clarification() -> None:
    context = resolve_trip_context(
        message="我现在出发要多久",
        intent="eta_query",
        calendar_state={"events": []},
        now_utc=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
        timezone_name="UTC",
        default_origin="Home",
    )
    assert context.needs_clarification is True
    assert context.clarification_question


def test_origin_user_vs_default() -> None:
    with_user_origin = resolve_trip_context(
        message="from campus to airport, how long",
        intent="eta_query",
        calendar_state={"events": []},
        now_utc=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
        timezone_name="UTC",
        default_origin="Home",
    )
    assert with_user_origin.origin_text == "campus"

    with_default_origin = resolve_trip_context(
        message="to airport how long",
        intent="eta_query",
        calendar_state={"events": []},
        now_utc=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
        timezone_name="UTC",
        default_origin="Home",
    )
    assert with_default_origin.origin_text == "Home"


def test_destination_strips_question_suffix() -> None:
    context = resolve_trip_context(
        message="去机场要多久",
        intent="eta_query",
        calendar_state={"events": []},
        now_utc=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
        timezone_name="UTC",
        default_origin="Home",
    )
    assert context.destination_text == "机场"


def test_destination_english_airport_works() -> None:
    context = resolve_trip_context(
        message="when can i get to airport",
        intent="eta_query",
        calendar_state={"events": []},
        now_utc=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
        timezone_name="UTC",
        default_origin="Home",
    )
    assert context.destination_text == "airport"
