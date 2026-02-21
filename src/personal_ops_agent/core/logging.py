from __future__ import annotations

import contextvars
import json
import logging
from datetime import datetime, timezone

_TRACE_ID: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")


class TraceIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = _TRACE_ID.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "trace_id": getattr(record, "trace_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def set_trace_id(trace_id: str) -> contextvars.Token:
    return _TRACE_ID.set(trace_id)


def reset_trace_id(token: contextvars.Token) -> None:
    _TRACE_ID.reset(token)


def configure_logging(level: str) -> None:
    root = logging.getLogger()
    if getattr(root, "_configured", False):
        root.setLevel(level)
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(TraceIDFilter())

    root.handlers = [handler]
    root.setLevel(level)
    root._configured = True
