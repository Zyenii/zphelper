from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel

from personal_ops_agent.core.settings import get_settings

logger = logging.getLogger(__name__)


class EtaConnectorError(RuntimeError):
    """Raised when ETA cannot be computed."""


class EtaPayload(BaseModel):
    eta_minutes: int
    peak: bool = False
    source: str = "mock"
    baseline_minutes: int | None = None
    traffic_delay_minutes: int | None = None
    traffic_ratio: float | None = None
    fetched_at_utc: str | None = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


_ETA_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def _make_cache_key(origin_text: str, destination_text: str, departure_time: datetime) -> str:
    bucket = departure_time.replace(minute=(departure_time.minute // 5) * 5, second=0, microsecond=0)
    return f"{origin_text}|{destination_text}|DRIVE|{bucket.isoformat()}"


def _parse_duration_to_minutes(raw: str | None) -> int | None:
    if not raw or not raw.endswith("s"):
        return None
    try:
        seconds = float(raw[:-1])
    except ValueError:
        return None
    return max(1, int(round(seconds / 60.0)))


def _looks_like_cjk(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value))


def _normalize_place_text(value: str) -> str:
    normalized = value.strip()
    lowered = normalized.lower()
    zh_map = {
        "纽约": "New York, NY, USA",
        "纽约市": "New York, NY, USA",
        "费城": "Philadelphia, PA, USA",
        "机场": "Philadelphia International Airport",
    }
    en_map = {
        "airport": "Philadelphia International Airport",
        "the airport": "Philadelphia International Airport",
        "phl": "Philadelphia International Airport",
        "jfk": "John F. Kennedy International Airport",
        "lga": "LaGuardia Airport",
        "ewr": "Newark Liberty International Airport",
        "new york": "New York, NY, USA",
        "nyc": "New York, NY, USA",
    }
    if normalized in zh_map:
        return zh_map[normalized]
    if lowered in en_map:
        return en_map[lowered]
    return normalized


def _candidate_addresses(value: str) -> list[str]:
    normalized = _normalize_place_text(value)
    candidates: list[str] = [normalized]
    lowered = normalized.lower()
    if "airport" in lowered and "usa" not in lowered:
        candidates.append(f"{normalized}, USA")
    if "new york" in lowered and "ny" not in lowered:
        candidates.append("New York, NY, USA")
    if "philadelphia" in lowered and "pa" not in lowered:
        candidates.append("Philadelphia, PA, USA")
    # preserve order while removing duplicates
    return list(dict.fromkeys(candidates))


def _load_mock_eta() -> dict[str, Any]:
    settings = get_settings()
    fixture_path = Path(settings.ETA_FIXTURE_PATH)
    if not fixture_path.is_absolute():
        fixture_path = _repo_root() / fixture_path
    if not fixture_path.exists():
        raise EtaConnectorError(f"ETA fixture not found: {fixture_path}")
    try:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EtaConnectorError(f"Invalid ETA fixture JSON: {fixture_path}") from exc
    return EtaPayload.model_validate(payload).model_dump()


def _read_heuristic_eta(depart_time: datetime) -> dict[str, Any]:
    settings = get_settings()
    hour = depart_time.hour
    peak = hour in {7, 8, 9, 17, 18, 19}
    eta_minutes = settings.ETA_BASE_MINUTES + (15 if peak else 0)
    return EtaPayload(
        eta_minutes=eta_minutes,
        peak=peak,
        source="heuristic",
        fetched_at_utc=datetime.now(timezone.utc).isoformat(),
    ).model_dump()


def _read_google_eta(origin_text: str, destination_text: str, depart_time: datetime) -> dict[str, Any]:
    settings = get_settings()
    api_key = settings.GOOGLE_ROUTES_API_KEY or settings.ROUTES_API
    if not api_key:
        raise EtaConnectorError("GOOGLE_ROUTES_API_KEY/ROUTES_API is required for google ETA mode.")

    origin_candidates = _candidate_addresses(origin_text)
    destination_candidates = _candidate_addresses(destination_text)
    language_code = "zh-CN" if (_looks_like_cjk(origin_text) or _looks_like_cjk(destination_text)) else "en-US"

    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    min_departure_utc = now_utc + timedelta(minutes=2)
    safe_departure = depart_time.astimezone(timezone.utc).replace(microsecond=0)
    if safe_departure <= min_departure_utc:
        safe_departure = min_departure_utc

    last_no_route_error: str | None = None
    first: dict[str, Any] | None = None
    for origin_candidate in origin_candidates:
        for destination_candidate in destination_candidates:
            body = {
                "origin": {"address": origin_candidate},
                "destination": {"address": destination_candidate},
                "travelMode": "DRIVE",
                "routingPreference": "TRAFFIC_AWARE",
                "computeAlternativeRoutes": False,
                "departureTime": safe_departure.isoformat().replace("+00:00", "Z"),
                "languageCode": language_code,
                "units": "METRIC",
                "regionCode": "US",
            }
            request = Request(
                "https://routes.googleapis.com/directions/v2:computeRoutes",
                data=json.dumps(body).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": api_key,
                    "X-Goog-FieldMask": "routes.duration,routes.staticDuration,routes.distanceMeters",
                },
                method="POST",
            )
            try:
                with urlopen(request, timeout=12) as response:  # noqa: S310
                    payload = json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                detail = ""
                try:
                    detail = exc.read().decode("utf-8", errors="replace").strip()
                except Exception:  # noqa: BLE001
                    detail = ""
                raise EtaConnectorError(f"Google ETA HTTP {exc.code}: {detail or exc.reason}") from exc
            except URLError as exc:
                raise EtaConnectorError(f"Google ETA request failed: {exc}") from exc

            routes = payload.get("routes", [])
            if routes:
                first = routes[0]
                break
            last_no_route_error = (
                f"Google ETA response has no routes for origin='{origin_candidate}' destination='{destination_candidate}'."
            )
        if first:
            break
    if not first:
        raise EtaConnectorError(last_no_route_error or "Google ETA response has no routes.")

    eta_minutes = _parse_duration_to_minutes(first.get("duration"))
    if eta_minutes is None:
        raise EtaConnectorError("Google ETA response missing duration.")
    baseline_minutes = _parse_duration_to_minutes(first.get("staticDuration"))
    delay = None
    ratio = None
    if baseline_minutes:
        delay = max(0, eta_minutes - baseline_minutes)
        ratio = eta_minutes / max(1, baseline_minutes)
    peak = bool((ratio and ratio >= 1.2) or (delay and delay >= 8))
    return EtaPayload(
        eta_minutes=eta_minutes,
        baseline_minutes=baseline_minutes,
        traffic_delay_minutes=delay,
        traffic_ratio=ratio,
        peak=peak,
        source="google",
        fetched_at_utc=datetime.now(timezone.utc).isoformat(),
    ).model_dump()


def get_eta(
    depart_time: datetime,
    origin_text: str | None = None,
    destination_text: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    provider = settings.ETA_PROVIDER or settings.ETA_MODE
    use_mock = settings.MOCK_ETA or provider == "mock"
    if use_mock:
        return _load_mock_eta()
    if provider == "google":
        if not origin_text or not destination_text:
            raise EtaConnectorError("origin_text and destination_text are required for google ETA mode.")
        cache_key = _make_cache_key(origin_text, destination_text, depart_time)
        now_ts = time.time()
        cached = _ETA_CACHE.get(cache_key)
        if cached and (now_ts - cached[0]) <= settings.ETA_CACHE_TTL_SECONDS:
            payload = dict(cached[1])
            payload["source"] = "cache"
            return payload
        try:
            payload = _read_google_eta(origin_text=origin_text, destination_text=destination_text, depart_time=depart_time)
            _ETA_CACHE[cache_key] = (now_ts, payload)
            return payload
        except EtaConnectorError as exc:
            logger.warning("eta.google_failed origin=%s destination=%s error=%s", origin_text, destination_text, exc)
            if cached:
                payload = dict(cached[1])
                payload["source"] = "cache"
                return payload
            raise
    return _read_heuristic_eta(depart_time=depart_time)
