from __future__ import annotations

import json
import logging
import time
from typing import Any
from socket import timeout as SocketTimeout
from urllib.error import URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.core.telemetry import record_llm_error, record_llm_usage, record_retry
from personal_ops_agent.planner.schemas import ExecutionPlan
from personal_ops_agent.router.intent import INTENT_DESCRIPTIONS, Intent

logger = logging.getLogger(__name__)

EXPLICIT_TRANSIT_KEYWORDS = {
    "transit",
    "public transit",
    "bus",
    "subway",
    "metro",
    "train",
    "公交",
    "地铁",
    "公共交通",
    "坐车",
}

EXPLICIT_WALKING_KEYWORDS = {
    "walk",
    "walking",
    "on foot",
    "步行",
    "走路",
}


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
    raise ValueError("No output text found in planner response")


def build_planner_prompt(max_actions: int, context: dict[str, Any] | None = None) -> str:
    tool_docs = "\n".join(
        [
            "- schedule_read: read calendar events for the relevant time window",
            "- schedule_summarize: summarize schedule and buffer suggestions",
            "- weather_read: fetch weather for relevant window",
            "- weather_summarize: summarize fetched weather",
            "- commute_plan: compute ETA / leave time / commute recommendation",
            "- todo_read: list current Todoist tasks",
            "- todo_parse: parse todo draft from user request",
            "- todo_write: write parsed todo to Todoist",
            "- checklist_generate: generate leaving checklist from calendar+weather+commute",
            "- calendar_create: create a calendar event",
        ]
    )
    intent_docs = "\n".join(f"- {item.value}: {INTENT_DESCRIPTIONS[item]}" for item in Intent)
    return (
        "You are a bounded execution planner for a personal operations assistant.\n"
        "Decide the user intent and the minimal ordered tool actions needed.\n"
        "Output strict JSON only. No markdown.\n"
        f"Use at most {max_actions} actions.\n"
        "Never invent tools outside the allowed list.\n"
        "If no supported workflow fits, choose intent unknown and set actions to an empty list.\n"
        "If the current request lacks required information, do not guess.\n"
        "Instead return status needs_clarification, list missing_slots, and provide one concise clarification_question.\n"
        "If continuation_context is present, treat the current user message as a possible answer to the unresolved task.\n"
        "If the information is now sufficient, return status ready.\n"
        "If the task still cannot be completed after repeated clarification, return status cannot_complete with no actions.\n"
        "Allowed intents:\n"
        f"{intent_docs}\n\n"
        "Allowed tools:\n"
        f"{tool_docs}\n\n"
        "Tool usage guidance:\n"
        "- schedule_summary usually uses [schedule_read, schedule_summarize]\n"
        "- weather_summary usually uses [weather_read, weather_summarize]\n"
        "- commute_advice usually uses [schedule_read, weather_read, commute_plan]\n"
        '- eta_query usually uses [commute_plan] and should include {"transport_mode":"driving","departure_time":"now"} unless the user explicitly asks for transit/walking\n'
        '- In Chinese, words like "交通", "去X要多久", "多久到" are ambiguous and should default to driving, not transit, unless the user explicitly says 公交/地铁/公共交通/步行\n'
        "- todo_list usually uses [todo_read]\n"
        "- todo_create usually uses [schedule_read, todo_parse, todo_write]\n"
        "- leaving_checklist usually uses [schedule_read, weather_read, commute_plan, checklist_generate]\n"
        "- calendar_create usually uses [calendar_create]\n"
        "- unknown should use no tool actions; use empty actions only for unknown\n"
        "Output schema:\n"
        '{"status":"ready","goal":"short goal","intent":"<intent>","actions":[{"tool":"schedule_read","args":{}}],"reason":"short reason","confidence":0.0,"missing_slots":[],"clarification_question":null,"known_slots":{}}\n'
        'Example eta_query: {"status":"ready","goal":"estimate driving eta","intent":"eta_query","actions":[{"tool":"commute_plan","args":{"destination":"New York","departure_time":"now","transport_mode":"driving"}}],"reason":"need real-time driving ETA","confidence":0.9,"missing_slots":[],"clarification_question":null,"known_slots":{"destination":"New York"}}\n'
        'Example clarification: {"status":"needs_clarification","goal":"estimate travel time","intent":"eta_query","actions":[],"reason":"destination missing","confidence":0.9,"missing_slots":["destination"],"clarification_question":"你想去哪里？","known_slots":{}}\n'
        'Example unknown: {"status":"cannot_complete","goal":"answer unsupported request","intent":"unknown","actions":[],"reason":"request is outside supported workflows","confidence":0.9,"missing_slots":[],"clarification_question":null,"known_slots":{}}\n'
        f"Context JSON:\n{json.dumps(context or {}, ensure_ascii=False)}\n"
    )


def _call_openai_planner(
    message: str,
    model: str,
    api_key: str,
    max_actions: int,
    context: dict[str, Any] | None = None,
) -> str:
    prompt = build_planner_prompt(max_actions=max_actions, context=context)
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
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        started_at = time.perf_counter()
        with urlopen(req, timeout=15) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, SocketTimeout, OSError) as exc:
        raise RuntimeError(f"planner network error: {exc}") from exc
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    record_llm_usage(model=model, usage=payload.get("usage"), latency_ms=latency_ms)
    return _extract_text_from_openai_response(payload)


def should_use_planner() -> bool:
    settings = get_settings()
    return bool(settings.LLM_PLANNER and settings.OPENAI_API_KEY)


def _normalize_unknown_plan(raw: ExecutionPlan) -> ExecutionPlan:
    if raw.intent == Intent.UNKNOWN.value:
        return ExecutionPlan(
            status="cannot_complete",
            goal=raw.goal or "handle unknown request",
            intent=Intent.UNKNOWN.value,
            actions=[],
            reason=raw.reason,
            confidence=raw.confidence,
            missing_slots=[],
            clarification_question=None,
            known_slots=raw.known_slots,
        )
    return raw


def _message_explicitly_requests_mode(message: str, *, mode: str) -> bool:
    lowered = message.lower()
    keywords = EXPLICIT_TRANSIT_KEYWORDS if mode == "transit" else EXPLICIT_WALKING_KEYWORDS
    return any(keyword in lowered or keyword in message for keyword in keywords)


def _normalize_eta_query_modes(raw: ExecutionPlan, message: str) -> ExecutionPlan:
    if raw.intent != Intent.ETA_QUERY.value:
        return raw

    normalized_actions: list[dict[str, Any]] = []
    changed = False
    for action in raw.actions:
        action_payload = action.model_dump()
        if action.tool != "commute_plan":
            normalized_actions.append(action_payload)
            continue

        args = dict(action.args)
        requested_mode = str(args.get("transport_mode", "")).strip().lower()
        if requested_mode in {"transit", "public_transit"} and not _message_explicitly_requests_mode(
            message,
            mode="transit",
        ):
            args["transport_mode"] = "driving"
            changed = True
        elif requested_mode in {"walking", "walk"} and not _message_explicitly_requests_mode(
            message,
            mode="walking",
        ):
            args["transport_mode"] = "driving"
            changed = True
        elif requested_mode == "":
            args["transport_mode"] = "driving"
            changed = True

        action_payload["args"] = args
        normalized_actions.append(action_payload)

    if not changed:
        return raw

    return ExecutionPlan(
        goal=raw.goal,
        intent=raw.intent,
        actions=normalized_actions,
        reason=raw.reason,
        confidence=raw.confidence,
    )


def make_plan(message: str, context: dict[str, Any] | None = None) -> ExecutionPlan | None:
    settings = get_settings()
    if not should_use_planner():
        return None

    attempts = 2
    for attempt in range(1, attempts + 1):
        try:
            raw = _call_openai_planner(
                message=message,
                model=settings.LLM_PLANNER_MODEL,
                api_key=settings.OPENAI_API_KEY or "",
                max_actions=settings.LLM_PLANNER_MAX_ACTIONS,
                context=context,
            )
            parsed = ExecutionPlan.model_validate(json.loads(raw))
            parsed = _normalize_unknown_plan(parsed)
            parsed = _normalize_eta_query_modes(parsed, message)
            if len(parsed.actions) > settings.LLM_PLANNER_MAX_ACTIONS:
                raise ValueError("planner exceeded max actions")
            if parsed.confidence < settings.LLM_PLANNER_THRESHOLD:
                return None
            return parsed
        except (RuntimeError, ValidationError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("planner.failed attempt=%s error=%s", attempt, exc)
            record_retry("planner", str(exc))
            if attempt == attempts:
                record_llm_error("planner_failed_after_retries")
                return None
    return None
