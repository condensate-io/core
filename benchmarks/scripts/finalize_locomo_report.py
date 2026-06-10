#!/usr/bin/env python3
"""Merge condensate sidecar into master report and regenerate comparative artifacts."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "benchmarks" / "results"
MASTER = RESULTS / "locomo10_full_report.json"
COMP_MD = RESULTS / "locomo10_comparative_report.md"
COMP_HTML = RESULTS / "locomo10_comparative_report.html"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sidecar",
        type=Path,
        default=RESULTS / "locomo10_condensate_v53_full.json",
        help="Condensate-only run JSON to merge",
    )
    args = parser.parse_args()
    if not args.sidecar.exists():
        print(f"Missing sidecar: {args.sidecar}", file=sys.stderr)
        return 1
    if not MASTER.exists():
        print(f"Missing master report: {MASTER}", file=sys.stderr)
        return 1

    merge_cmd = [
        sys.executable,
        str(ROOT / "benchmarks" / "scripts" / "merge_locomo_reports.py"),
        "--base",
        str(MASTER),
        "--sidecar",
        str(args.sidecar),
        "--output",
        str(MASTER),
    ]
    report_cmd = [
        sys.executable,
        str(ROOT / "benchmarks" / "runners" / "generate_comparative_report.py"),
        "--input",
        str(MASTER),
        "--output",
        str(COMP_MD),
    ]
    html_cmd = [
        sys.executable,
        str(ROOT / "benchmarks" / "scripts" / "render_report_html.py"),
    ]
    for cmd in (merge_cmd, report_cmd, html_cmd):
        print("Running:", " ".join(cmd), file=sys.stderr)
        subprocess.run(cmd, cwd=ROOT, check=True)
    print(f"Updated {MASTER}, {COMP_MD}, {COMP_HTML}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
