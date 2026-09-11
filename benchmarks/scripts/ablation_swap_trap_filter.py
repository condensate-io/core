"""LOC-028d: quantify non-adversarial recovery when RETRIEVE_SWAP_TRAP_FILTER=0.

Compares two LoCoMo report JSONs (filter on vs off) and prints per-category deltas,
emphasizing single-hop, open-domain, temporal, and multi-hop (non-adversarial slices).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

NON_ADVERSARIAL = ("single-hop", "open-domain", "temporal", "multi-hop")


def _load_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["backends"]["condensate"]["summary"]


def _category_accuracy(summary: dict[str, Any], category: str) -> tuple[int, int, float]:
    bucket = summary.get("by_category", {}).get(category, {})
    total = int(bucket.get("total", 0))
    hits = int(bucket.get("hits", 0))
    accuracy = float(bucket.get("accuracy", 0.0))
    return hits, total, accuracy


def _slice_accuracy(report_path: Path, sample_id: str) -> tuple[int, int, float]:
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    for sample in payload["backends"]["condensate"].get("sample_reports", []):
        if str(sample.get("sample_id", "")) != sample_id:
            continue
        summary = sample.get("summary", {})
        total = int(summary.get("total", 0))
        hits = int(summary.get("retrieval_hits", 0))
        accuracy = float(summary.get("retrieval_accuracy", 0.0))
        return hits, total, accuracy
    return 0, 0, 0.0


def compare_reports(filter_on: Path, filter_off: Path, *, slices: tuple[str, ...]) -> int:
    on_summary = _load_summary(filter_on)
    off_summary = _load_summary(filter_off)

    print(f"Filter ON:  {filter_on}")
    print(f"Filter OFF: {filter_off}")
    print()

    on_overall = float(on_summary.get("retrieval_accuracy", 0.0))
    off_overall = float(off_summary.get("retrieval_accuracy", 0.0))
    print(
        f"Overall: {off_overall:.4f} (off) vs {on_overall:.4f} (on) "
        f"Δ={off_overall - on_overall:+.4f}"
    )

    non_adv_recovery = 0.0
    print("\nNon-adversarial categories (recovery when filter OFF):")
    for category in NON_ADVERSARIAL:
        on_hits, on_total, on_acc = _category_accuracy(on_summary, category)
        off_hits, off_total, off_acc = _category_accuracy(off_summary, category)
        delta = off_acc - on_acc
        if category != "adversarial":
            non_adv_recovery += delta
        print(
            f"  {category:12} {off_hits}/{off_total} ({100 * off_acc:.1f}%) vs "
            f"{on_hits}/{on_total} ({100 * on_acc:.1f}%) Δ={delta:+.4f}"
        )

    on_adv_hits, on_adv_total, on_adv_acc = _category_accuracy(on_summary, "adversarial")
    off_adv_hits, off_adv_total, off_adv_acc = _category_accuracy(off_summary, "adversarial")
    print(
        f"\n  adversarial   {off_adv_hits}/{off_adv_total} ({100 * off_adv_acc:.1f}%) vs "
        f"{on_adv_hits}/{on_adv_total} ({100 * on_adv_acc:.1f}%) "
        f"Δ={off_adv_acc - on_adv_acc:+.4f}"
    )

    print(f"\nSum non-adversarial Δ (pts): {non_adv_recovery:+.4f}")

    if slices:
        print("\nConversation slices:")
        for sid in slices:
            off_h, off_t, off_a = _slice_accuracy(filter_off, sid)
            on_h, on_t, on_a = _slice_accuracy(filter_on, sid)
            print(
                f"  {sid}: off {off_h}/{off_t} ({100 * off_a:.1f}%) vs "
                f"on {on_h}/{on_t} ({100 * on_a:.1f}%) Δ={off_a - on_a:+.4f}"
            )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--filter-on",
        type=Path,
        default=Path("benchmarks/results/locomo_mini_swap_trap_on.json"),
    )
    parser.add_argument(
        "--filter-off",
        type=Path,
        default=Path("benchmarks/results/locomo_mini_swap_trap_off.json"),
    )
    parser.add_argument(
        "--slices",
        nargs="*",
        default=["conv-26"],
        help="Sample IDs for slice comparison (default: conv-26)",
    )
    args = parser.parse_args()

    for path in (args.filter_on, args.filter_off):
        if not path.exists():
            print(f"Report not found: {path}", file=sys.stderr)
            return 1

    return compare_reports(args.filter_on, args.filter_off, slices=tuple(args.slices))


if __name__ == "__main__":
    raise SystemExit(main())
