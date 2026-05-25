import json
import os
import threading
import time
from typing import Dict, Tuple

_lock = threading.Lock()
_cache: Dict[str, Tuple[dict, float]] = {}


def load_json_config(path: str, ttl_seconds: int = 30) -> dict:
    normalized = os.path.abspath(path)
    now = time.monotonic()

    with _lock:
        entry = _cache.get(normalized)
        if entry is not None:
            data, expires_at = entry
            if now < expires_at:
                return data

    if not os.path.exists(path):
        data: dict = {}
    else:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    with _lock:
        _cache[normalized] = (data, time.monotonic() + ttl_seconds)

    return data


def invalidate_json_config(path: str) -> None:
    normalized = os.path.abspath(path)
    with _lock:
        _cache.pop(normalized, None)
