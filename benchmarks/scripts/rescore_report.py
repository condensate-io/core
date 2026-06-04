#!/usr/bin/env python3
"""Re-score a LoCoMo report JSON with current qa.py metrics (no re-retrieve)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmarks.data.locomo_loader import get_qa_pairs, load_samples, turn_lookup
from benchmarks.metrics.qa import grade_answer, score_qa, summarize_qa_results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, default=Path("benchmarks/data/locomo10.json"))
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    samples = {s["sample_id"]: s for s in load_samples(args.dataset)}
    for backend in payload.get("backends", {}).values():
        all_rows: list[dict] = []
        for sample_report in backend.get("sample_reports", []):
            sample = samples[sample_report["sample_id"]]
            lookup = turn_lookup(sample["conversation"])
            qa_by_q = {q["question"]: q for q in get_qa_pairs(sample)}
            rescored: list[dict] = []
            for row in sample_report.get("qa_results", []):
                qa = qa_by_q[row["question"]]
                context = row.get("native_answer") or row.get("context") or ""
                scored = score_qa(context, qa, lookup)
                scored["retrieved_tokens"] = row.get("retrieved_tokens")
                scored["native_answer"] = row.get("native_answer")
                native_ok, method = grade_answer(scored["native_answer"] or "", qa.get("answer", ""))
                scored["native_correct"] = native_ok
                scored["native_grading_method"] = method
                rescored.append(scored)
            sample_report["qa_results"] = rescored
            sample_report["summary"] = summarize_qa_results(rescored)
            all_rows.extend(rescored)
        backend["summary"] = summarize_qa_results(all_rows)
    print(json.dumps(payload["backends"]["condensate"]["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
