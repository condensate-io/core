"""Structured memory backend — returns only active assertions (simulates Condensate supersession)."""

from __future__ import annotations

from benchmarks.backends.base import MemoryBackend
from benchmarks.metrics.tokens import count_tokens


class StructuredMemoryBackend:
    """Stores facts with status; search returns active facts only."""

    def __init__(self) -> None:
        self._sessions: dict[str, list[dict]] = {}

    def reset(self, session_id: str) -> None:
        self._sessions[session_id] = []

    def add(self, session_id: str, messages: list[dict]) -> None:
        bucket = self._sessions.setdefault(session_id, [])
        for msg in messages:
            bucket.append(
                {
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                    "status": msg.get("status", "active"),
                }
            )

    def search(self, session_id: str, query: str) -> str:
        messages = self._sessions.get(session_id, [])
        active = [m for m in messages if m.get("status") == "active"]
        lines = [f"{m['role']}: {m['content']}" for m in active]
        return "\n".join(lines)

    def token_count(self, text: str) -> int:
        return count_tokens(text)


def satisfies_memory_backend(obj: object) -> bool:
    return isinstance(obj, MemoryBackend)
