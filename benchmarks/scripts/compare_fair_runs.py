"""Compare two LoCoMo fair-run JSON reports."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from benchmarks.metrics.qa import answer_in_context
from src.retrieve.entity_alignment import is_entity_swap_trap, is_specific_attribute_query


def flatten(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = [
        qa
        for sample in data["backends"]["condensate"]["sample_reports"]
        for qa in sample["qa_results"]
    ]
    return {r["question"]: r for r in rows}


def _retrieved_context(row: dict) -> str:
    return str(row.get("native_answer") or row.get("context") or "")


def tag_loss(prev_row: dict, curr_row: dict, question: str) -> str:
    """LOC-029: classify prev-hit → curr-miss regressions."""
    category = curr_row.get("category", "")
    evidence_ids = list(curr_row.get("evidence_ids") or [])
    context = _retrieved_context(curr_row)
    evidence_recall = float(curr_row.get("evidence_recall") or 0.0)
    answer = curr_row.get("answer")

    if category == "multi-hop" and len(evidence_ids) >= 2:
        if evidence_recall < 1.0:
            return "multi_evidence_miss"

    if is_entity_swap_trap(question) and prev_row.get("retrieval_hit"):
        return "trap_filter"

    if "[observation" in context.lower() and evidence_ids:
        missing_turns = [
            eid
            for eid in evidence_ids
            if eid not in context and f"[source turn {eid}]" not in context
        ]
        if missing_turns and answer and not answer_in_context(answer, context):
            return "hydration_miss"

    if evidence_recall > 0 and not curr_row.get("retrieval_hit"):
        return "ranking_miss"

    if prev_row.get("retrieval_hit") and not curr_row.get("retrieval_hit"):
        return "ingest_variance"

    return "ingest_variance"


def main() -> None:
    prev = flatten(ROOT / "benchmarks/results/locomo10_condensate_v53_fair_prev.json")
    curr = flatten(ROOT / "benchmarks/results/locomo10_condensate_v53_fair.json")

    for cat in ("adversarial", "open-domain", "multi-hop", "single-hop", "temporal"):
        total = sum(1 for r in curr.values() if r["category"] == cat)
        p = sum(
            1
            for q, r in prev.items()
            if r["category"] == cat and r["retrieval_hit"]
        )
        c = sum(
            1
            for q, r in curr.items()
            if r["category"] == cat and r["retrieval_hit"]
        )
        print(f"{cat:12} {p}/{total} ({100*p/total:.1f}%) -> {c}/{total} ({100*c/total:.1f}%)")

    adv_gain = [
        q
        for q, cr in curr.items()
        if prev.get(q, {}).get("category") == "adversarial"
        and not prev[q]["retrieval_hit"]
        and cr["retrieval_hit"]
    ]
    adv_loss = [
        q
        for q, cr in curr.items()
        if prev.get(q, {}).get("category") == "adversarial"
        and prev[q]["retrieval_hit"]
        and not cr["retrieval_hit"]
    ]
    print(f"\nadversarial +{len(adv_gain)} -{len(adv_loss)}")
    od_loss = [
        q
        for q, cr in curr.items()
        if prev.get(q, {}).get("category") == "open-domain"
        and prev[q]["retrieval_hit"]
        and not cr["retrieval_hit"]
    ]
    broad_od = sum(1 for q in od_loss if is_specific_attribute_query(q))
    narrow_od = sum(1 for q in od_loss if is_entity_swap_trap(q))
    print(f"open-domain -{len(od_loss)} (broad {broad_od}, narrow trap {narrow_od})")

    losses = [
        (q, tag_loss(prev[q], curr[q], q))
        for q, cr in curr.items()
        if prev.get(q, {}).get("retrieval_hit") and not cr["retrieval_hit"]
    ]
    if losses:
        print("\nLoss tags (prev hit → curr miss):")
        tag_counts: dict[str, int] = {}
        for question, tag in losses:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        for tag, count in sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"  {tag:22} {count}")
        print("\nSample tagged losses:")
        for question, tag in losses[:8]:
            print(f"  [{tag}] {question[:90]}")


if __name__ == "__main__":
    main()
