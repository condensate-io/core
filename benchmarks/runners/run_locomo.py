#!/usr/bin/env python3
"""LoCoMo runner skeleton — demonstrates backend add/search cycle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from benchmarks.backends.condensate import CondensateBackend
from benchmarks.backends.full_context import FullContextBackend


SAMPLE_MESSAGES = [
    {"role": "user", "content": "My name is Alex and I live in Seattle."},
    {"role": "assistant", "content": "Nice to meet you, Alex!"},
    {"role": "user", "content": "I prefer PostgreSQL over MySQL for new projects."},
]

SAMPLE_QUERY = "What database does Alex prefer?"


def build_backend(name: str):
    if name == "full_context":
        return FullContextBackend()
    if name == "condensate":
        return CondensateBackend()
    raise ValueError(f"Unknown backend: {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Condensate benchmark runner (LoCoMo scaffold)")
    parser.add_argument("--backend", choices=["condensate", "full_context"], default="full_context")
    parser.add_argument("--session-id", default="demo-session")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    backend = build_backend(args.backend)
    session_id = args.session_id

    backend.reset(session_id)
    backend.add(session_id, SAMPLE_MESSAGES)
    context = backend.search(session_id, SAMPLE_QUERY)
    tokens = backend.token_count(context)

    result = {
        "backend": args.backend,
        "session_id": session_id,
        "query": SAMPLE_QUERY,
        "retrieved_context": context,
        "retrieved_context_tokens": tokens,
        "note": "LoCoMo dataset wiring not yet connected — this run validates the backend lifecycle.",
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"\nWrote {args.output}", file=sys.stderr)

    if hasattr(backend, "close"):
        backend.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
