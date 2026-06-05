"""Full-context baseline — returns entire transcript without retrieval."""

from __future__ import annotations

from benchmarks.metrics.tokens import count_tokens


class FullContextBackend:
    """Stores messages in memory; search returns concatenated transcript."""

    def __init__(self) -> None:
        self._sessions: dict[str, list[dict]] = {}

    def reset(self, session_id: str) -> None:
        self._sessions[session_id] = []

    def add(self, session_id: str, messages: list[dict]) -> None:
        bucket = self._sessions.setdefault(session_id, [])
        bucket.extend(messages)

    def search(self, session_id: str, query: str) -> str:
        del query
        messages = self._sessions.get(session_id, [])
        lines: list[str] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def token_count(self, text: str) -> int:
        return count_tokens(text)
