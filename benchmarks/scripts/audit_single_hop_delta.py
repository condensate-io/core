"""LOC-028c: bucket single-hop prev→current fair-run losses."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from benchmarks.scripts.compare_fair_runs import flatten, tag_loss
from src.retrieve.entity_alignment import is_entity_swap_trap, is_specific_attribute_query
from src.retrieve.router import observation_line_thin_for_query, query_suggests_verbatim_detail


def bucket_loss(question: str, prev_row: dict, curr_row: dict) -> str:
    tag = tag_loss(prev_row, curr_row, question)
    if tag in ("hydration_miss", "multi_evidence_miss"):
        return tag
    if is_entity_swap_trap(question):
        return "trap_collateral"
    if is_specific_attribute_query(question) and tag == "trap_filter":
        return "trap_collateral"
    context = str(curr_row.get("native_answer") or "")
    if "[observation" in context.lower() and query_suggests_verbatim_detail(question):
        if any(
            observation_line_thin_for_query(question, line)
            for line in context.split("\n")
            if "[observation" in line.lower()
        ):
            return "observation_only"
    if tag == "ranking_miss":
        return "ranking"
    return tag


def main() -> None:
    prev = flatten(ROOT / "benchmarks/results/locomo10_condensate_v53_fair_prev.json")
    curr = flatten(ROOT / "benchmarks/results/locomo10_condensate_v53_fair.json")

    losses = [
        (q, bucket_loss(q, prev[q], curr[q]))
        for q, cr in curr.items()
        if prev.get(q, {}).get("category") == "single-hop"
        and prev[q]["retrieval_hit"]
        and not cr["retrieval_hit"]
    ]

    counts: dict[str, int] = {}
    for _, bucket in losses:
        counts[bucket] = counts.get(bucket, 0) + 1

    print(f"single-hop losses (prev hit → curr miss): {len(losses)}")
    for bucket, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {bucket:22} {count}")

    print("\nTop bucket samples:")
    top = max(counts, key=counts.get) if counts else ""
    shown = 0
    for question, bucket in losses:
        if bucket != top:
            continue
        print(f"  - {question[:100]}")
        shown += 1
        if shown >= 8:
            break


if __name__ == "__main__":
    main()
