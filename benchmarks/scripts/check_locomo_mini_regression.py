"""LOC-027: Block regressions on locomo_mini condensate retrieval vs pinned baselines."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASELINE = ROOT / "benchmarks/results/baselines/locomo_mini_condensate_baseline.json"
DEFAULT_PEAK = ROOT / "benchmarks/results/baselines/locomo10_condensate_v53_fair_peak.json"
DEFAULT_CURRENT = ROOT / "benchmarks/results/locomo10_condensate_v53_fair.json"

OVERALL_DROP_LIMIT = 0.02
CATEGORY_DROP_LIMIT = 0.03


def _condensate_summary(report: dict[str, Any]) -> dict[str, Any]:
    backend = report["backends"]["condensate"]
    return backend["summary"]


def _category_accuracy(summary: dict[str, Any], category: str) -> float:
    bucket = summary.get("by_category", {}).get(category, {})
    return float(bucket.get("accuracy", 0.0))


def check_regression(
    current: dict[str, Any],
    baseline: dict[str, Any],
    *,
    overall_drop_limit: float = OVERALL_DROP_LIMIT,
    category_drop_limit: float = CATEGORY_DROP_LIMIT,
    label: str = "baseline",
) -> list[str]:
    cur = _condensate_summary(current)
    base = _condensate_summary(baseline)
    failures: list[str] = []

    cur_overall = float(cur.get("retrieval_accuracy", 0.0))
    base_overall = float(base.get("retrieval_accuracy", 0.0))
    if cur_overall < base_overall - overall_drop_limit:
        failures.append(
            f"{label}: overall {cur_overall:.4f} dropped >{overall_drop_limit:.2f} "
            f"from {base_overall:.4f}"
        )

    categories = set(cur.get("by_category", {})) | set(base.get("by_category", {}))
    for category in sorted(categories):
        cur_acc = _category_accuracy(cur, category)
        base_acc = _category_accuracy(base, category)
        if cur_acc < base_acc - category_drop_limit:
            failures.append(
                f"{label}: {category} {cur_acc:.4f} dropped >{category_drop_limit:.2f} "
                f"from {base_acc:.4f}"
            )

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--current",
        type=Path,
        required=True,
        help="Current LoCoMo report JSON (mini or full)",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help="Pinned locomo_mini condensate baseline",
    )
    parser.add_argument(
        "--peak",
        type=Path,
        default=DEFAULT_PEAK,
        help="Pinned peak fair-run summary baseline",
    )
    parser.add_argument(
        "--fair-current",
        type=Path,
        default=DEFAULT_CURRENT,
        help="Current full fair-run JSON for category floor checks",
    )
    parser.add_argument(
        "--skip-fair",
        action="store_true",
        help="Only compare against locomo_mini baseline",
    )
    args = parser.parse_args()

    current = json.loads(args.current.read_text(encoding="utf-8"))
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    failures = check_regression(current, baseline, label="mini")

    if not args.skip_fair and args.peak.exists() and args.fair_current.exists():
        peak = json.loads(args.peak.read_text(encoding="utf-8"))
        fair_current = json.loads(args.fair_current.read_text(encoding="utf-8"))
        failures.extend(check_regression(fair_current, peak, label="fair-vs-peak"))

    if failures:
        print("LoCoMo regression gate FAILED:", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1

    cur = _condensate_summary(current)
    print(
        f"LoCoMo regression gate OK — overall {cur.get('retrieval_accuracy', 0.0):.4f} "
        f"({cur.get('retrieval_hits', 0)}/{cur.get('total', 0)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
