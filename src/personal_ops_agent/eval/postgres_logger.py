from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from personal_ops_agent.core.settings import get_settings

logger = logging.getLogger(__name__)

_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS agent_run_logs (
  id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  trace_id TEXT,
  flow TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  tokens INTEGER,
  latency_ms INTEGER,
  tool_success BOOLEAN,
  validation_errors TEXT,
  confidence DOUBLE PRECISION,
  extra_json JSONB
);
"""

_INSERT_SQL = """
INSERT INTO agent_run_logs
(created_at, trace_id, flow, prompt_version, tokens, latency_ms, tool_success, validation_errors, confidence, extra_json)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb);
"""


def log_run_event(
    *,
    flow: str,
    trace_id: str | None,
    prompt_version: str,
    tokens: int | None,
    latency_ms: int | None,
    tool_success: bool,
    validation_errors: str | None,
    confidence: float | None,
    extra: dict[str, Any] | None = None,
) -> None:
    settings = get_settings()
    if not settings.DATABASE_URL:
        return
    try:
        import psycopg
    except ImportError:
        logger.warning("postgres_logger.disabled reason=missing_psycopg")
        return

    payload_json = json.dumps(extra or {}, ensure_ascii=False)
    try:
        with psycopg.connect(settings.DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(_TABLE_SQL)
                cur.execute(
                    _INSERT_SQL,
                    (
                        datetime.now(timezone.utc),
                        trace_id,
                        flow,
                        prompt_version,
                        tokens,
                        latency_ms,
                        tool_success,
                        validation_errors,
                        confidence,
                        payload_json,
                    ),
                )
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("postgres_logger.failed flow=%s error=%s", flow, exc)
