from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from personal_ops_agent.core.settings import get_settings


def _store_path() -> Path:
    return Path(get_settings().SESSION_CONTEXT_STORE_PATH)


def _load_all() -> dict[str, Any]:
    path = _store_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_all(data: dict[str, Any]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_continuation(session_id: str) -> dict[str, Any] | None:
    data = _load_all()
    item = data.get(session_id)
    if not isinstance(item, dict) or not item.get("active"):
        return None
    return item


def save_continuation(session_id: str, continuation: dict[str, Any]) -> None:
    data = _load_all()
    data[session_id] = continuation
    _save_all(data)


def clear_continuation(session_id: str) -> None:
    data = _load_all()
    if session_id not in data:
        return
    del data[session_id]
    _save_all(data)
