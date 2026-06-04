#!/usr/bin/env python3
"""Drop stale v1 condensate results; optionally seed completed samples from sample report."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FULL = ROOT / "benchmarks/results/locomo10_full_report.json"
SAMPLE = ROOT / "benchmarks/results/locomo10_condensate_sample.json"


def main() -> int:
    full = json.loads(FULL.read_text(encoding="utf-8"))
    full["backends"].pop("condensate", None)
    full.pop("condensate_strengths", None)

    seeded: list[str] = []
    if SAMPLE.exists():
        sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
        cond = sample.get("backends", {}).get("condensate", {})
        reports = cond.get("sample_reports", [])
        if reports:
            full.setdefault("backends", {})["condensate"] = {
                "backend": "condensate",
                "samples": len(reports),
                "sample_reports": reports,
                "summary": cond.get("summary", {}),
            }
            seeded = [r["sample_id"] for r in reports]

    FULL.write_text(json.dumps(full, indent=2), encoding="utf-8")
    print(f"Prepared {FULL.name}: removed v1 condensate", file=sys.stderr)
    if seeded:
        print(f"Seeded completed samples: {', '.join(seeded)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
