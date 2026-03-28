from __future__ import annotations

import json
import logging
import time
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.core.telemetry import record_llm_error, record_llm_usage

logger = logging.getLogger(__name__)


class LocationExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: str | None = None
    destination: str | None = None
    confidence: float
    reason: str

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        if not (0.0 <= value <= 1.0):
            raise ValueError("confidence must be in [0,1]")
        return value


def _extract_text_from_openai_response(payload: dict[str, Any]) -> str:
    output = payload.get("output", [])
    for item in output:
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return str(content.get("text", ""))
    text = payload.get("output_text")
    if isinstance(text, str):
        return text
    raise ValueError("No output text found in location extractor response")


def build_location_prompt(message: str) -> str:
    return (
        "You extract commute origin and destination from a user message.\n"
        "Output strict JSON only. No markdown.\n"
        "If destination is not present, set it to null.\n"
        "If origin is not present, set it to null.\n"
        "Keep extracted place text concise and literal.\n"
        "Schema:\n"
        '{"origin":null,"destination":"string or null","confidence":0.0,"reason":"short"}\n'
        "Examples:\n"
        'Input: "我现在去chengdu famous food要多久" -> {"origin":null,"destination":"chengdu famous food","confidence":0.9,"reason":"destination is explicitly stated after 去"}\n'
        'Input: "from campus to jfk how long" -> {"origin":"campus","destination":"jfk","confidence":0.95,"reason":"contains explicit from/to"}\n'
        'Input: "要多久" -> {"origin":null,"destination":null,"confidence":0.2,"reason":"missing destination"}\n'
        f"User: {message}"
    )


def _call_openai_location_extractor(message: str, model: str, api_key: str) -> str:
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": build_location_prompt(message)}]},
        ],
    }
    req = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        started_at = time.perf_counter()
        with urlopen(req, timeout=12) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(f"location extractor network error: {exc}") from exc
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    record_llm_usage(model=model, usage=payload.get("usage"), latency_ms=latency_ms)
    return _extract_text_from_openai_response(payload)


def extract_locations_llm(message: str) -> LocationExtractionResult | None:
    settings = get_settings()
    if not (settings.LLM_LOCATION_EXTRACTOR and settings.OPENAI_API_KEY):
        return None
    try:
        raw = _call_openai_location_extractor(
            message=message,
            model=settings.LLM_LOCATION_EXTRACTOR_MODEL,
            api_key=settings.OPENAI_API_KEY,
        )
        parsed = LocationExtractionResult.model_validate(json.loads(raw))
        if parsed.confidence < settings.LLM_LOCATION_EXTRACTOR_THRESHOLD:
            return None
        return parsed
    except (RuntimeError, ValidationError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("location_extractor.failed error=%s", exc)
        record_llm_error("location_extractor_failed")
        return None
