"""Token counting helpers for benchmark metrics."""

from __future__ import annotations

import tiktoken


def count_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    """Return token count using tiktoken cl100k_base (offline-safe for Docker CI)."""
    del model  # cl100k_base matches gpt-4o-mini family for benchmark comparisons
    if not text:
        return 0
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)
