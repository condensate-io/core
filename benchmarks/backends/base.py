"""Memory backend protocol for Condensate benchmark harness."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class MemoryBackend(Protocol):
    """Lifecycle expected by LoCoMo / LongMemEval runners."""

    def reset(self, session_id: str) -> None:
        """Clear all stored state for a benchmark session."""

    def add(self, session_id: str, messages: list[dict]) -> None:
        """Ingest conversation turns (role/content dicts)."""

    def search(self, session_id: str, query: str) -> str:
        """Return retrieved context string for the answerer LLM."""

    def token_count(self, text: str) -> int:
        """Count tokens in retrieved context (primary efficiency metric)."""
