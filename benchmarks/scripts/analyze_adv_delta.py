"""Compare adversarial delta between two fair-run JSON files."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.retrieve.entity_alignment import is_specific_attribute_query
from src.retrieve.recall_gate import is_adversarial_phrasing


def flatten_qa(data: dict) -> list[dict]:
    rows: list[dict] = []
    for sample in data["backends"]["condensate"].get("sample_reports", []):
        for qa in sample.get("qa_results", []):
            rows.append(qa)
    return rows


def main() -> None:
    prev_path = ROOT / "benchmarks/results/locomo10_condensate_v53_fair_prev.json"
    curr_path = ROOT / "benchmarks/results/locomo10_condensate_v53_fair.json"
    prev = flatten_qa(json.loads(prev_path.read_text(encoding="utf-8")))
    curr = flatten_qa(json.loads(curr_path.read_text(encoding="utf-8")))

    def find(rows: list[dict], substr: str) -> list[dict]:
        return [
            r
            for r in rows
            if substr.lower() in r.get("question", "").lower()
            and r.get("category") == "adversarial"
        ]

    traps = [
        "necklace symbolize",
        "grandma from",
        "counseling workshop",
        "instrument does",
        "Oscar Melanie",
        "camping trip",
        "road trip accident",
    ]
    print("=== Canonical swap trap status ===")
    for t in traps:
        pr = find(prev, t)
        cr = find(curr, t)
        for p, c in zip(pr or [{}], cr or [{}]):
            q = (c or p).get("question", "")[:70]
            ph = p.get("retrieval_hit") if p else None
            ch = c.get("retrieval_hit") if c else None
            print(f"{t:25} prev={ph} curr={ch} | {q}")

    fail = [r for r in curr if r.get("category") == "adversarial" and not r.get("retrieval_hit")]
    swap_fail = [r for r in fail if is_specific_attribute_query(r.get("question", ""))]
    print(f"\nRemaining adv failures: {len(fail)}")
    print(f"Detected as swap trap: {len(swap_fail)} ({100 * len(swap_fail) / len(fail):.0f}%)")

    buckets: Counter[str] = Counter()
    for r in fail:
        q = r.get("question", "")
        lowered = q.lower()
        if is_specific_attribute_query(q):
            buckets["detected_swap"] += 1
        elif is_adversarial_phrasing(q):
            buckets["counterfactual"] += 1
        elif "'s" in q:
            buckets["possessive_undetected"] += 1
        elif " did " in lowered or " does " in lowered:
            buckets["activity_undetected"] += 1
        else:
            buckets["other"] += 1
    print("Failure buckets:", dict(buckets))

    print("\nUndetected possessive failures (sample):")
    n = 0
    for r in fail:
        q = r.get("question", "")
        if not is_specific_attribute_query(q) and "'s" in q:
            n += 1
            if n <= 12:
                print("-", q[:95])


if __name__ == "__main__":
    main()
