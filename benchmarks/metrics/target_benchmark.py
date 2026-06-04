"""Published LoCoMo leaderboard numbers used as the accuracy/token target benchmark."""

from __future__ import annotations

from typing import Any

# Source: published LoCoMo memory-system research (industry reference leaderboard).
TARGET_BENCHMARK_PUBLISHED: dict[str, Any] = {
    "locomo_overall_pct": 92.5,
    "locomo_tokens_mean": 6956,
    "locomo_full_context_tokens": 25000,
    "locomo_categories": {
        "single-hop": 92.3,
        "multi-hop": 93.3,
        "open-domain": 76.0,
        "temporal": 92.8,
    },
    "longmemeval_overall_pct": 94.4,
    "longmemeval_tokens_mean": 6787,
    "source_note": "Published LoCoMo memory-system leaderboard (external reference)",
}

TARGET_BENCHMARK_LABEL = "Target benchmark"
TARGET_BENCHMARK_SHORT = "target benchmark"
