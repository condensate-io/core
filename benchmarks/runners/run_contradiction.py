#!/usr/bin/env python3
"""Run ContradictionBench against full-context vs structured backends."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from benchmarks.backends.full_context import FullContextBackend
from benchmarks.backends.structured import StructuredMemoryBackend
from benchmarks.data.generate_contradiction_cases import load_cases
from benchmarks.metrics.contradiction import score_case, summarize_results


def run_backend(backend_name: str, cases: list[dict]) -> list[dict]:
    if backend_name == "full_context":
        backend = FullContextBackend()
    elif backend_name == "structured":
        backend = StructuredMemoryBackend()
    else:
        raise ValueError(f"Unknown backend: {backend_name}")

    results: list[dict] = []
    for case in cases:
        session_id = case["id"]
        backend.reset(session_id)
        backend.add(session_id, case["messages"])
        context = backend.search(session_id, case["query"])
        scored = score_case(context, case)
        scored["backend"] = backend_name
        scored["retrieved_context_tokens"] = backend.token_count(context)
        results.append(scored)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="ContradictionBench runner")
    parser.add_argument(
        "--backend",
        choices=["full_context", "structured", "both"],
        default="both",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    cases = load_cases()
    backends = ["full_context", "structured"] if args.backend == "both" else [args.backend]

    report: dict = {"cases": len(cases), "backends": {}}
    for name in backends:
        results = run_backend(name, cases)
        report["backends"][name] = {
            "summary": summarize_results(results),
            "results": results,
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["backends"], indent=2))
    print(f"\nWrote {args.output}", file=sys.stderr)

    if args.backend == "both":
        structured = report["backends"]["structured"]["summary"]
        if structured["passed"] != structured["total"]:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
