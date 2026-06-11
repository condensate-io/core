"""Validate LoCoMo retrieval on high-loss conversation slices (LOC-028c / Phase 0)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_SLICES = ("conv-26", "conv-41", "conv-49")
DEFAULT_REPORT = Path("benchmarks/results/locomo10_condensate_v53_fair.json")


def slice_accuracy(report_path: Path, sample_ids: tuple[str, ...]) -> dict[str, dict]:
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    backend = payload["backends"]["condensate"]
    out: dict[str, dict] = {}
    for sample in backend.get("sample_reports", []):
        sid = str(sample.get("sample_id", ""))
        if sid not in sample_ids:
            continue
        summary = sample.get("summary", {})
        out[sid] = {
            "total": summary.get("total", 0),
            "hits": summary.get("retrieval_hits", 0),
            "accuracy": summary.get("retrieval_accuracy", 0.0),
            "by_category": summary.get("by_category", {}),
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--slices", nargs="*", default=list(DEFAULT_SLICES))
    parser.add_argument("--min-accuracy", type=float, default=0.0)
    args = parser.parse_args()

    if not args.report.exists():
        print(f"Report not found: {args.report}", file=sys.stderr)
        return 1

    stats = slice_accuracy(args.report, tuple(args.slices))
    missing = [s for s in args.slices if s not in stats]
    if missing:
        print(f"Missing sample reports: {', '.join(missing)}", file=sys.stderr)

    failures: list[str] = []
    for sid in args.slices:
        row = stats.get(sid)
        if not row:
            continue
        acc = float(row["accuracy"])
        print(
            f"{sid}: {row['hits']}/{row['total']} ({100 * acc:.1f}%)"
        )
        if acc < args.min_accuracy:
            failures.append(f"{sid} below floor {args.min_accuracy:.2f}")

    if failures:
        for line in failures:
            print(f"FAIL: {line}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
