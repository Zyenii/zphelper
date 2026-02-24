from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel

from personal_ops_agent.core.settings import get_settings


class WeatherConnectorError(RuntimeError):
    """Raised when weather data cannot be fetched or parsed."""


class WeatherPoint(BaseModel):
    time: str
    rain_probability: int
    apparent_temperature: float
    wind_kph: float


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_mock_weather() -> dict[str, Any]:
    settings = get_settings()
    fixture_path = Path(settings.WEATHER_FIXTURE_PATH)
    if not fixture_path.is_absolute():
        fixture_path = _repo_root() / fixture_path
    if not fixture_path.exists():
        raise WeatherConnectorError(f"Weather fixture not found: {fixture_path}")
    try:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WeatherConnectorError(f"Invalid weather fixture JSON: {fixture_path}") from exc
    points = payload.get("points", [])
    validated = [WeatherPoint.model_validate(item).model_dump() for item in points]
    return {"summary": payload.get("summary", ""), "points": validated}


def _read_open_meteo_weather(window_start_utc: datetime, window_end_utc: datetime, timezone_name: str) -> dict[str, Any]:
    settings = get_settings()
    if window_end_utc <= window_start_utc:
        raise WeatherConnectorError("Invalid weather window: end must be after start.")
    try:
        request_tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        request_tz = timezone.utc

    now_local = datetime.now(timezone.utc).astimezone(request_tz)
    window_end_local = window_end_utc.astimezone(request_tz)
    day_span = (window_end_local.date() - now_local.date()).days + 1
    forecast_days = max(1, min(16, day_span))
    params = urlencode(
        {
            "latitude": settings.WEATHER_LATITUDE,
            "longitude": settings.WEATHER_LONGITUDE,
            "hourly": "precipitation_probability,apparent_temperature,wind_speed_10m",
            "forecast_days": forecast_days,
            "timezone": timezone_name,
        }
    )
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    try:
        with urlopen(url, timeout=10) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise WeatherConnectorError(f"Failed to fetch weather: {exc}") from exc

    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    rain = hourly.get("precipitation_probability", [])
    temp = hourly.get("apparent_temperature", [])
    wind = hourly.get("wind_speed_10m", hourly.get("windspeed_10m", []))
    try:
        local_tz = ZoneInfo(payload.get("timezone", timezone_name))
    except ZoneInfoNotFoundError:
        local_tz = timezone.utc

    window_start_local = window_start_utc.astimezone(local_tz)
    window_end_local = window_end_utc.astimezone(local_tz)
    points = []
    for idx, when in enumerate(times):
        try:
            local_dt = datetime.fromisoformat(when).replace(tzinfo=local_tz)
            if not (window_start_local <= local_dt < window_end_local):
                continue
            points.append(
                WeatherPoint(
                    time=local_dt.isoformat(),
                    rain_probability=int(rain[idx]),
                    apparent_temperature=float(temp[idx]),
                    wind_kph=float(wind[idx]),
                ).model_dump()
            )
        except Exception:
            continue
    if not points:
        return {"summary": "No weather data available for the selected window.", "points": []}

    max_rain = max((item["rain_probability"] for item in points), default=0)
    max_wind = max((item["wind_kph"] for item in points), default=0.0)
    avg_temp = round(sum((item["apparent_temperature"] for item in points), 0.0) / len(points), 1)
    summary = (
        f"Open-Meteo selected window ({len(points)} point(s)): "
        f"rain max {max_rain}%, avg feels-like {avg_temp}C, wind max {max_wind:.1f}kph."
    )
    return {"summary": summary, "points": points}


def get_weather(
    window_start_utc: datetime | None = None,
    window_end_utc: datetime | None = None,
    timezone_name: str = "UTC",
    hours: int = 6,
) -> dict[str, Any]:
    settings = get_settings()
    use_mock = settings.MOCK_WEATHER or settings.WEATHER_MODE == "mock"
    if window_start_utc is None:
        window_start_utc = datetime.now(timezone.utc)
    if window_end_utc is None:
        window_end_utc = window_start_utc + timedelta(hours=max(1, hours))
    if use_mock:
        payload = _load_mock_weather()
        points = payload.get("points", [])
        filtered = []
        for point in points:
            try:
                value = point["time"]
                if value.endswith("Z"):
                    value = value[:-1] + "+00:00"
                dt = datetime.fromisoformat(value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if window_start_utc <= dt.astimezone(timezone.utc) < window_end_utc:
                    filtered.append(point)
            except Exception:
                continue
        if not filtered:
            filtered = points
        payload["points"] = filtered
        return payload
    return _read_open_meteo_weather(
        window_start_utc=window_start_utc,
        window_end_utc=window_end_utc,
        timezone_name=timezone_name,
    )
