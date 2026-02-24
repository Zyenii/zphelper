from datetime import timedelta, timezone

from personal_ops_agent.timewindow.rules import parse_time_window_rule, resolve_now_local


def _to_local(window, timezone_name: str):
    del timezone_name
    tz = timezone(timedelta(hours=-5))
    return window.start_utc.astimezone(tz), window.end_utc.astimezone(tz)


def test_rule_today_and_tomorrow() -> None:
    tz = "America/New_York"
    now_local = resolve_now_local(tz, "2026-02-18T09:30:00-05:00")

    today = parse_time_window_rule("今天有什么安排", now_local, tz)
    assert today is not None
    start_local, end_local = _to_local(today, tz)
    assert start_local.isoformat() == "2026-02-18T00:00:00-05:00"
    assert end_local.isoformat() == "2026-02-19T00:00:00-05:00"

    tomorrow = parse_time_window_rule("what is my schedule tomorrow", now_local, tz)
    assert tomorrow is not None
    start_local, end_local = _to_local(tomorrow, tz)
    assert start_local.isoformat() == "2026-02-19T00:00:00-05:00"
    assert end_local.isoformat() == "2026-02-20T00:00:00-05:00"


def test_rule_week_and_weekend() -> None:
    tz = "America/New_York"
    now_local = resolve_now_local(tz, "2026-02-18T09:30:00-05:00")  # Wednesday

    this_week = parse_time_window_rule("本周安排", now_local, tz)
    assert this_week is not None
    start_local, end_local = _to_local(this_week, tz)
    assert start_local.isoformat() == "2026-02-16T00:00:00-05:00"
    assert end_local.isoformat() == "2026-02-23T00:00:00-05:00"

    weekend = parse_time_window_rule("这周末有什么安排", now_local, tz)
    assert weekend is not None
    start_local, end_local = _to_local(weekend, tz)
    assert start_local.isoformat() == "2026-02-21T00:00:00-05:00"
    assert end_local.isoformat() == "2026-02-23T00:00:00-05:00"


def test_rule_next_n_days_and_utc_conversion() -> None:
    tz = "America/New_York"
    now_local = resolve_now_local(tz, "2026-02-18T09:30:00-05:00")
    window = parse_time_window_rule("Can you show my schedule for the next 3 days?", now_local, tz)
    assert window is not None

    start_local, end_local = _to_local(window, tz)
    assert start_local.isoformat() == "2026-02-18T00:00:00-05:00"
    assert end_local.isoformat() == "2026-02-21T00:00:00-05:00"

    assert window.start_utc.isoformat() == "2026-02-18T05:00:00+00:00"
    assert window.end_utc.isoformat() == "2026-02-21T05:00:00+00:00"


def test_rule_day_of_month_with_period() -> None:
    tz = "America/New_York"
    now_local = resolve_now_local(tz, "2026-02-23T09:30:00-05:00")
    window = parse_time_window_rule("25号晚上天气怎么样", now_local, tz)
    assert window is not None
    start_local, end_local = _to_local(window, tz)
    assert start_local.isoformat() == "2026-02-25T18:00:00-05:00"
    assert end_local.isoformat() == "2026-02-25T22:00:00-05:00"
