#!/usr/bin/env python3
"""Merge LoCoMo benchmark sidecar JSON files into a canonical report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmarks.metrics.report import build_strength_summary


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def merge_reports(base: dict[str, Any], *sidecars: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    merged.setdefault("backends", {})
    for sidecar in sidecars:
        for name, backend_report in sidecar.get("backends", {}).items():
            merged["backends"][name] = backend_report
        if sidecar.get("grader"):
            merged["grader"] = sidecar["grader"]
        if sidecar.get("grading_policy"):
            merged["grading_policy"] = sidecar["grading_policy"]
    merged["condensate_strengths"] = build_strength_summary(merged["backends"])
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge LoCoMo benchmark JSON reports")
    parser.add_argument("--base", type=Path, required=True, help="Canonical report to update")
    parser.add_argument("--sidecar", type=Path, action="append", default=[], help="Report to merge in")
    parser.add_argument("--output", type=Path, default=None, help="Output path (default: overwrite --base)")
    args = parser.parse_args()

    base = load_json(args.base) if args.base.exists() else {}
    sidecars = [load_json(path) for path in args.sidecar]
    merged = merge_reports(base, *sidecars)

    output = args.output or args.base
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    print(f"Merged {len(args.sidecar)} sidecar(s) into {output}")
    print(f"Backends: {', '.join(sorted(merged.get('backends', {}).keys()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
