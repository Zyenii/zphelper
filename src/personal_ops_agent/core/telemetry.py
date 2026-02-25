from __future__ import annotations

import contextvars
import logging
from dataclasses import asdict, dataclass
from typing import Any

from personal_ops_agent.core.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class RuntimeStats:
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    retry_count: int = 0


_RUNTIME_STATS: contextvars.ContextVar[RuntimeStats] = contextvars.ContextVar("runtime_stats", default=RuntimeStats())


def reset_runtime_stats() -> contextvars.Token:
    return _RUNTIME_STATS.set(RuntimeStats())


def restore_runtime_stats(token: contextvars.Token) -> None:
    _RUNTIME_STATS.reset(token)


def _extract_usage_counts(usage: dict[str, Any] | None) -> tuple[int, int, int]:
    if not isinstance(usage, dict):
        return 0, 0, 0
    input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens))
    return input_tokens, output_tokens, total_tokens


def record_llm_usage(*, model: str, usage: dict[str, Any] | None) -> None:
    stats = _RUNTIME_STATS.get()
    input_tokens, output_tokens, total_tokens = _extract_usage_counts(usage)
    settings = get_settings()
    input_cost = (input_tokens / 1000.0) * float(getattr(settings, "OPENAI_INPUT_COST_PER_1K_USD", 0.0))
    output_cost = (output_tokens / 1000.0) * float(getattr(settings, "OPENAI_OUTPUT_COST_PER_1K_USD", 0.0))
    stats.llm_calls += 1
    stats.input_tokens += input_tokens
    stats.output_tokens += output_tokens
    stats.total_tokens += total_tokens
    stats.estimated_cost_usd += input_cost + output_cost
    logger.info(
        "telemetry.llm_usage model=%s input_tokens=%s output_tokens=%s total_tokens=%s estimated_cost_usd=%.6f",
        model,
        input_tokens,
        output_tokens,
        total_tokens,
        input_cost + output_cost,
    )


def record_retry(component: str, reason: str) -> None:
    stats = _RUNTIME_STATS.get()
    stats.retry_count += 1
    logger.info("telemetry.retry component=%s reason=%s count=%s", component, reason, stats.retry_count)


def get_runtime_stats() -> dict[str, Any]:
    stats = _RUNTIME_STATS.get()
    payload = asdict(stats)
    payload["estimated_cost_usd"] = round(float(payload["estimated_cost_usd"]), 6)
    return payload
