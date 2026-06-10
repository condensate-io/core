"""Compare two LoCoMo fair-run JSON reports."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.retrieve.entity_alignment import is_entity_swap_trap, is_specific_attribute_query


def flatten(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = [
        qa
        for sample in data["backends"]["condensate"]["sample_reports"]
        for qa in sample["qa_results"]
    ]
    return {r["question"]: r for r in rows}


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


if __name__ == "__main__":
    main()
