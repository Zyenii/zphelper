from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.router.intent import INTENT_DESCRIPTIONS, Intent, all_intent_values

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMRouteResult:
    intent: str
    confidence: float
    reason: str


class RouterOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str
    confidence: float
    reason: str

    @field_validator("intent")
    @classmethod
    def validate_intent(cls, value: str) -> str:
        if value not in all_intent_values():
            raise ValueError("intent must be a supported enum value")
        return value

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        if not (0.0 <= value <= 1.0):
            raise ValueError("confidence must be within [0,1]")
        return value


def build_router_prompt() -> str:
    intent_definitions = "\n".join(f"- {key.value}: {desc}" for key, desc in INTENT_DESCRIPTIONS.items())
    return (
        "You are an intent classifier for a personal operations assistant.\n"
        "Pick exactly one intent from the allowed list.\n"
        "If uncertain or ambiguous, choose unknown.\n\n"
        "Allowed intents:\n"
        f"{intent_definitions}\n\n"
        "Output strict JSON only with exactly these keys and no extra keys:\n"
        '{"intent":"<intent>","confidence":0.0,"reason":"<short reason>"}\n'
        "No markdown, no code fences, no commentary.\n\n"
        "Examples:\n"
        'Input: "What is my schedule tomorrow?" -> {"intent":"schedule_summary","confidence":0.93,"reason":"asks for agenda"}\n'
        'Input: "我今天都有什么安排？" -> {"intent":"schedule_summary","confidence":0.92,"reason":"询问日程安排"}\n'
        'Input: "When should I leave for my next meeting?" -> {"intent":"commute_advice","confidence":0.9,"reason":"asks departure timing"}\n'
        'Input: "我现在出门要不要带伞？" -> {"intent":"commute_advice","confidence":0.9,"reason":"通勤与天气建议"}\n'
        'Input: "Tell me a joke" -> {"intent":"unknown","confidence":0.9,"reason":"outside supported intents"}'
    )


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
    raise ValueError("No output text found in LLM response")


def _call_openai_classifier(message: str, model: str, api_key: str) -> str:
    prompt = build_router_prompt()
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": prompt}]},
            {"role": "user", "content": [{"type": "input_text", "text": message}]},
        ],
    }
    req = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=12) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(f"LLM router network error: {exc}") from exc
    return _extract_text_from_openai_response(payload)


def parse_llm_router_output(raw_text: str) -> LLMRouteResult:
    parsed = json.loads(raw_text)
    if not isinstance(parsed, dict):
        raise ValueError("LLM output must be a JSON object")
    validated = RouterOutput.model_validate(parsed)
    return LLMRouteResult(
        intent=validated.intent,
        confidence=validated.confidence,
        reason=validated.reason,
    )


def llm_route(message: str) -> LLMRouteResult:
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        return LLMRouteResult(intent=Intent.UNKNOWN.value, confidence=0.0, reason="missing_api_key")
    try:
        raw = _call_openai_classifier(message, settings.LLM_ROUTER_MODEL, settings.OPENAI_API_KEY)
        result = parse_llm_router_output(raw)
    except (RuntimeError, ValidationError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("llm_router.failed error=%s", exc)
        return LLMRouteResult(intent=Intent.UNKNOWN.value, confidence=0.0, reason="llm_error")

    if result.confidence < settings.LLM_ROUTER_THRESHOLD:
        return LLMRouteResult(intent=Intent.UNKNOWN.value, confidence=result.confidence, reason="low_confidence")
    return result
