from __future__ import annotations

import json
import logging
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.core.telemetry import record_llm_usage

logger = logging.getLogger(__name__)


def _extract_text(payload: dict[str, Any]) -> str:
    output = payload.get("output", [])
    for item in output:
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return str(content.get("text", "")).strip()
    text = payload.get("output_text")
    if isinstance(text, str):
        return text.strip()
    return ""


def generate_unknown_reply(user_message: str) -> str | None:
    settings = get_settings()
    if not settings.UNKNOWN_LLM_REPLY or not settings.OPENAI_API_KEY:
        return None

    body = {
        "model": settings.UNKNOWN_LLM_MODEL,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You are a concise personal ops assistant. "
                            "For unknown requests, reply helpfully and ask one clarifying question if needed. "
                            "No markdown."
                        ),
                    }
                ],
            },
            {"role": "user", "content": [{"type": "input_text", "text": user_message}]},
        ],
    }
    req = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=12) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        logger.warning("unknown_reply.failed error=%s", exc)
        return None
    record_llm_usage(model=settings.UNKNOWN_LLM_MODEL, usage=payload.get("usage"))
    text = _extract_text(payload)
    return text or None
