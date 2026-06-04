"""LoCoMo-style observations corpus baseline (assertion-like facts, not raw transcript)."""

from __future__ import annotations

from benchmarks.metrics.tokens import count_tokens


class ObservationsBackend:
    """Stores condensed session observations; mimics LoCoMo RAG over fact DB."""

    def __init__(self) -> None:
        self._sessions: dict[str, list[str]] = {}

    def reset(self, session_id: str) -> None:
        self._sessions[session_id] = []

    def add(self, session_id: str, messages: list[dict]) -> None:
        bucket = self._sessions.setdefault(session_id, [])
        for msg in messages:
            content = msg.get("content", "")
            if content:
                bucket.append(content)

    def load_observations(self, session_id: str, observations: list[str]) -> None:
        self._sessions[session_id] = list(observations)

    def search(self, session_id: str, query: str) -> str:
        observations = self._sessions.get(session_id, [])
        if not observations:
            return ""
        query_terms = {t.lower() for t in query.split() if len(t) > 2}
        if not query_terms:
            return "\n".join(observations)
        ranked = sorted(
            observations,
            key=lambda obs: sum(1 for term in query_terms if term in obs.lower()),
            reverse=True,
        )
        return "\n".join(ranked)

    def token_count(self, text: str) -> int:
        return count_tokens(text)
