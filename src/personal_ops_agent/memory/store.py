from __future__ import annotations

import json
from pathlib import Path

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.memory.schemas import DEFAULT_MEMORY, PersonalMemory


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_memory_path() -> Path:
    settings = get_settings()
    path = Path(settings.MEMORY_STORE_PATH)
    if not path.is_absolute():
        path = _repo_root() / path
    return path


def ensure_memory_store() -> Path:
    path = resolve_memory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(DEFAULT_MEMORY.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_memory() -> PersonalMemory:
    settings = get_settings()
    if not settings.MEMORY_ENABLED:
        return DEFAULT_MEMORY.model_copy(deep=True)

    path = ensure_memory_store()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return DEFAULT_MEMORY.model_copy(deep=True)
    return PersonalMemory.model_validate(payload)


def save_memory(memory: PersonalMemory) -> Path:
    path = ensure_memory_store()
    path.write_text(memory.model_dump_json(indent=2), encoding="utf-8")
    return path
