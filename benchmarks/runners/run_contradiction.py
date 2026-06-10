"""ContradictionBench runner — structured memory with superseded/active filtering."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from benchmarks.data.generate_contradiction_cases import load_cases
from benchmarks.backends.structured import StructuredMemoryBackend
from benchmarks.metrics.qa import summarize_qa_results


def run_contradiction(cases_path: Path | None = None) -> dict:
    cases = load_cases(cases_path)
    backend = StructuredMemoryBackend()
    results: list[dict] = []

    for case in cases:
        session_id = str(case["id"])
        backend.reset(session_id)
        backend.add(session_id, case["messages"])
        context = backend.search(session_id, case["query"])
        forbidden = case.get("forbidden_in_context") or []
        trap_hits = [f for f in forbidden if f.lower() in context.lower()]
        expected = case.get("expected_active_only", "")
        active_present = expected.lower() in context.lower() if expected else True
        results.append(
            {
                "case_id": session_id,
                "query": case["query"],
                "category": "contradiction",
                "memory_type": "contradiction_resolution",
                "retrieval_hit": active_present and not trap_hits,
                "forbidden_leaked": bool(trap_hits),
                "evidence_recall": 1.0 if active_present else 0.0,
                "question": case["query"],
                "answer": expected,
            }
        )

    summary = summarize_qa_results(results)
    summary["cases"] = len(cases)
    summary["forbidden_leaks"] = sum(1 for r in results if r.get("forbidden_leaked"))
    return {"summary": summary, "results": results}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ContradictionBench cases")
    parser.add_argument(
        "--cases",
        type=Path,
        default=None,
        help="Path to contradiction_cases.json",
    )
    parser.add_argument("--output", type=Path, default=None, help="Write JSON report")
    parser.add_argument(
        "--backend",
        default="structured",
        choices=["structured", "both"],
        help="Backend selector (both runs structured-only today)",
    )
    args = parser.parse_args()

    report = run_contradiction(args.cases)
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)
    summary = report["summary"]
    passed = summary.get("retrieval_hits", 0)
    total = summary.get("total", 0)
    leaks = summary.get("forbidden_leaks", 0)
    print(
        f"[contradiction] retrieval {passed}/{total}, forbidden leaks={leaks}",
        file=sys.stderr,
    )
    return 0 if leaks == 0 and passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
