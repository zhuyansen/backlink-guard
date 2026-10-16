"""Paid answers kept on disk for a few days, so checking the same site twice in a week
is paid for once. One JSON file per question under <state>/cache/."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from . import state_dir

DAY = 86400
TTL_DAYS = 7


def _dir() -> Path:
    return state_dir() / "cache"


def _path(key: str) -> Path:
    return _dir() / (hashlib.sha1(key.encode()).hexdigest()[:20] + ".json")


def get(key: str, ttl_days: float = TTL_DAYS):
    path = _path(key)
    if not path.exists() or time.time() - path.stat().st_mtime > ttl_days * DAY:
        return None
    try:
        return json.loads(path.read_text())
    except ValueError:
        return None


def put(key: str, value) -> None:
    _dir().mkdir(parents=True, exist_ok=True)
    _path(key).write_text(json.dumps(value, ensure_ascii=False))
