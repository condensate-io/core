#!/usr/bin/env python3
"""Download the public LoCoMo dataset (CC BY-NC 4.0) — not a fork of mem0 benchmarks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

DEFAULT_URL = (
    "https://raw.githubusercontent.com/snap-research/LoCoMo/main/data/locomo10.json"
)
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "data" / "locomo10.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch snap-research LoCoMo dataset")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    response = httpx.get(args.url, timeout=120.0, follow_redirects=True)
    response.raise_for_status()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(response.content)
    print(f"Downloaded LoCoMo dataset to {args.output}", file=sys.stderr)
    print(f"Run with: LOCOMO_DATA_PATH={args.output} make test-locomo-full", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
