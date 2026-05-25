"""Token counting helpers for benchmark metrics."""

from __future__ import annotations

import tiktoken


def count_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    """Return token count using tiktoken (same family as Mem0 benchmark reports)."""
    if not text:
        return 0
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))
