"""Memory backend protocol for Condensate benchmark harness."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class MemoryBackend(Protocol):
    def reset(self, session_id: str) -> None: ...

    def add(self, session_id: str, messages: list[dict]) -> None: ...

    def search(self, session_id: str, query: str) -> str: ...

    def token_count(self, text: str) -> int: ...
