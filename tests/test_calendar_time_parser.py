from datetime import datetime, timezone

from personal_ops_agent.calendar.time_parser import parse_calendar_datetime_rule


def test_parse_calendar_datetime_rule_chinese_relative_time() -> None:
    now_local = datetime(2026, 2, 25, 10, 0, tzinfo=timezone.utc)
    parsed = parse_calendar_datetime_rule("明天晚上7点半定位马路边", now_local=now_local)
    assert parsed is not None
    assert parsed.start.year == 2026
    assert parsed.start.month == 2
    assert parsed.start.day == 26
    assert parsed.start.hour == 19
    assert parsed.start.minute == 30
    assert parsed.end > parsed.start


def test_parse_calendar_datetime_rule_iso() -> None:
    now_local = datetime(2026, 2, 25, 10, 0, tzinfo=timezone.utc)
    parsed = parse_calendar_datetime_rule(
        "create event team sync 2026-03-01 10:00 2026-03-01 11:00",
        now_local=now_local,
    )
    assert parsed is not None
    assert parsed.start.hour == 10
    assert parsed.end.hour == 11
