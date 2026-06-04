#!/usr/bin/env python3
"""LoCoMo benchmark runner — multi-backend evaluation with checkpoint/resume."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from benchmarks.backends.registry import build_backend
from benchmarks.data.locomo_loader import (
    conversation_to_messages,
    full_transcript_tokens_hint,
    get_qa_pairs,
    load_samples,
    sample_observations,
    turn_lookup,
)
from benchmarks.metrics.judge import AnswerGrader
from benchmarks.metrics.qa import grade_answer, score_qa, summarize_qa_results
from benchmarks.metrics.report import build_strength_summary, merge_backend_summary

DEFAULT_BACKEND_ORDER = ["full_context", "observations", "structured", "condensate"]

GRADING_POLICY: dict[str, str] = {
    "full_context": "retrieval_only — LLM grade skipped (context too large for judge)",
    "observations": "retrieval_only",
    "structured": "retrieval_only",
    "condensate": "retrieval + native_answer (+ optional --llm-grade on short strings)",
}


def resolve_backends(spec: str, *, skip_condensate: bool = False) -> list[str]:
    if spec == "all":
        names = list(DEFAULT_BACKEND_ORDER)
        if skip_condensate and "condensate" in names:
            names.remove("condensate")
        return names
    return [spec]


def backend_is_complete(report: dict[str, Any], backend_name: str, samples: list[dict]) -> bool:
    backend_data = report.get("backends", {}).get(backend_name)
    if not backend_data:
        return False
    sample_reports = backend_data.get("sample_reports", [])
    if len(sample_reports) != len(samples):
        return False
    expected_ids = {s["sample_id"] for s in samples}
    got_ids = {sr["sample_id"] for sr in sample_reports}
    return expected_ids == got_ids


def score_row(
    backend_name: str,
    backend: Any,
    session_id: str,
    qa: dict[str, Any],
    turn_lookup_map: dict[str, str],
    grader: AnswerGrader,
    *,
    llm_grade: bool = False,
) -> dict[str, Any]:
    context = backend.search(session_id, qa["question"])
    scored = score_qa(context, qa, turn_lookup_map)
    scored["retrieved_tokens"] = backend.token_count(context)
    scored["native_answer"] = context
    native_ok, method = grade_answer(context, qa.get("answer", ""))
    scored["native_correct"] = native_ok
    scored["native_grading_method"] = method
    if hasattr(backend, "last_strategy"):
        scored["strategy"] = backend.last_strategy

    if llm_grade and backend_name != "full_context":
        gold = qa.get("answer", "")
        if qa.get("adversarial"):
            trap = qa.get("adversarial_trap", gold)
            result = grader.grade(
                qa["question"],
                gold,
                context,
                adversarial=True,
                adversarial_trap=str(trap),
            )
        else:
            result = grader.grade(qa["question"], str(gold), context)
        scored["graded_correct"] = result.correct
        scored["grading_method"] = result.grading_method
    return scored


def _ingest_sample(backend_name: str, backend: Any, session_id: str, sample: dict[str, Any]) -> None:
    if backend_name == "observations":
        backend.reset(session_id)
        backend.load_observations(session_id, sample_observations(sample))
        return
    if backend_name == "condensate":
        backend.reset(session_id)
        backend.ingest_sample(session_id, sample)
        return
    messages = conversation_to_messages(sample["conversation"])
    backend.reset(session_id)
    backend.add(session_id, messages)


def run_backend(
    backend_name: str,
    samples: list[dict[str, Any]],
    *,
    resume: bool = False,
    resume_sample_reports: list[dict[str, Any]] | None = None,
    llm_grade: bool = False,
    limit_samples: int | None = None,
    checkpoint_path: Path | None = None,
    checkpoint_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if limit_samples is not None:
        samples = samples[:limit_samples]

    backend = build_backend(backend_name)  # type: ignore[arg-type]
    grader = AnswerGrader(use_llm_fallback=llm_grade)
    completed: dict[str, dict[str, Any]] = {}
    if resume and resume_sample_reports:
        completed = {sr["sample_id"]: sr for sr in resume_sample_reports}

    sample_reports: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []
    token_samples: list[int] = []
    transcript_tokens_total = 0

    try:
        for sample in samples:
            sample_id = sample["sample_id"]
            if sample_id in completed:
                sample_reports.append(completed[sample_id])
                all_rows.extend(completed[sample_id].get("qa_results", []))
                summary = completed[sample_id].get("summary", {})
                if summary.get("avg_retrieved_tokens"):
                    token_samples.extend(
                        [summary["avg_retrieved_tokens"]] * summary.get("total", 1)
                    )
                transcript_tokens_total += summary.get("avg_transcript_tokens", 0)
                continue

            session_id = sample_id
            ingest_started = time.perf_counter()
            skip_ingest = os.getenv("CONDENSATE_SKIP_INGEST", "").lower() in ("1", "true", "yes")
            if not skip_ingest:
                print(f"[locomo] ingesting {sample_id}...", file=sys.stderr, flush=True)
                _ingest_sample(backend_name, backend, session_id, sample)
            elif backend_name == "condensate":
                backend.reset(session_id)
            ingest_ms = round((time.perf_counter() - ingest_started) * 1000, 2)
            if skip_ingest:
                print(f"[locomo] {sample_id} skip ingest, scoring QA...", file=sys.stderr, flush=True)
            else:
                print(
                    f"[locomo] {sample_id} ingest done ({ingest_ms:.0f}ms), scoring QA...",
                    file=sys.stderr,
                    flush=True,
                )

            turns = turn_lookup(sample["conversation"])
            qa_pairs = get_qa_pairs(sample)
            qa_results: list[dict[str, Any]] = []
            sample_token_samples: list[int] = []
            for qi, qa in enumerate(qa_pairs, start=1):
                if qi == 1 or qi % 25 == 0 or qi == len(qa_pairs):
                    print(
                        f"[locomo] {sample_id} QA {qi}/{len(qa_pairs)}",
                        file=sys.stderr,
                        flush=True,
                    )
                row = score_row(
                    backend_name,
                    backend,
                    session_id,
                    qa,
                    turns,
                    grader,
                    llm_grade=llm_grade,
                )
                qa_results.append(row)
                sample_token_samples.append(row["retrieved_tokens"])

            qa_summary = summarize_qa_results(qa_results)
            transcript_tokens = full_transcript_tokens_hint(sample, backend.token_count)
            sample_summary = merge_backend_summary(qa_summary, sample_token_samples, transcript_tokens)
            sample_report = {
                "backend": backend_name,
                "sample_id": sample_id,
                "ingest_ms": ingest_ms,
                "summary": sample_summary,
                "qa_results": qa_results,
            }
            sample_reports.append(sample_report)
            all_rows.extend(qa_results)
            token_samples.extend(sample_token_samples)
            transcript_tokens_total += transcript_tokens

            if checkpoint_path is not None and checkpoint_meta is not None:
                partial_qa = summarize_qa_results(all_rows)
                partial_tokens = token_samples
                avg_transcript_partial = (
                    round(transcript_tokens_total / len(sample_reports), 2) if sample_reports else 0
                )
                partial_overall = merge_backend_summary(
                    partial_qa, partial_tokens, int(avg_transcript_partial)
                )
                partial_report = {
                    "backend": backend_name,
                    "samples": len(samples),
                    "summary": partial_overall,
                    "sample_reports": sample_reports,
                }
                checkpoint = {**checkpoint_meta, "backends": {backend_name: partial_report}}
                checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
                checkpoint_path.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")
                acc = sample_summary.get("retrieval_accuracy", 0)
                print(
                    f"[locomo] checkpoint {sample_id} -> {checkpoint_path} "
                    f"({acc:.1%} on {len(qa_pairs)} QA)",
                    file=sys.stderr,
                    flush=True,
                )
    finally:
        if hasattr(backend, "close"):
            backend.close()

    overall_qa = summarize_qa_results(all_rows)
    avg_transcript = round(transcript_tokens_total / len(samples), 2) if samples else 0
    overall = merge_backend_summary(overall_qa, token_samples, int(avg_transcript))
    return {
        "backend": backend_name,
        "samples": len(samples),
        "summary": overall,
        "sample_reports": sample_reports,
    }


def _load_existing_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="LoCoMo multi-backend benchmark runner")
    parser.add_argument("--backend", default="all", help="Backend name or 'all'")
    parser.add_argument("--dataset", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--skip-condensate", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--llm-grade", action="store_true")
    parser.add_argument("--limit-samples", type=int, default=None)
    parser.add_argument(
        "--sample-ids",
        type=str,
        default=None,
        help="Comma-separated sample_id filter (e.g. conv-30,conv-41)",
    )
    args = parser.parse_args()

    samples = load_samples(args.dataset)
    if args.sample_ids:
        wanted = {s.strip() for s in args.sample_ids.split(",") if s.strip()}
        samples = [s for s in samples if s["sample_id"] in wanted]
        if not samples:
            print(f"No samples matched --sample-ids {args.sample_ids}", file=sys.stderr)
            return 1
    elif args.limit_samples:
        samples = samples[: args.limit_samples]

    backend_names = resolve_backends(args.backend, skip_condensate=args.skip_condensate)
    existing = _load_existing_report(args.output) if args.resume else {}
    backends_out: dict[str, Any] = dict(existing.get("backends", {}))

    for backend_name in backend_names:
        resume_reports = None
        if args.resume and backend_name in backends_out:
            if backend_is_complete(existing, backend_name, samples):
                continue
            resume_reports = backends_out[backend_name].get("sample_reports")

        report = run_backend(
            backend_name,
            samples,
            resume=args.resume,
            resume_sample_reports=resume_reports,
            llm_grade=args.llm_grade,
            limit_samples=args.limit_samples,
            checkpoint_path=args.output,
            checkpoint_meta={
                "benchmark": "locomo",
                "harness": "condensate-native",
                "scoring": "retrieval + native_answer + optional_llm_grade",
                "dataset": str(args.dataset or "benchmarks/data/locomo_mini.json"),
                "samples_evaluated": len(samples),
                "total_qa_pairs": sum(len(get_qa_pairs(s)) for s in samples),
                "grading_policy": GRADING_POLICY,
            },
        )
        backends_out[backend_name] = report

        checkpoint = {
            "benchmark": "locomo",
            "harness": "condensate-native",
            "scoring": "retrieval + native_answer + optional_llm_grade",
            "dataset": str(args.dataset or "benchmarks/data/locomo_mini.json"),
            "samples_evaluated": len(samples),
            "total_qa_pairs": sum(len(get_qa_pairs(s)) for s in samples),
            "backends": backends_out,
            "grading_policy": GRADING_POLICY,
            "condensate_strengths": build_strength_summary(backends_out),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")
        print(f"Checkpoint: {backend_name} complete -> {args.output}", file=sys.stderr)

    final = {
        "benchmark": "locomo",
        "harness": "condensate-native",
        "scoring": "retrieval + native_answer + optional_llm_grade",
        "dataset": str(args.dataset or "benchmarks/data/locomo_mini.json"),
        "samples_evaluated": len(samples),
        "total_qa_pairs": sum(len(get_qa_pairs(s)) for s in samples),
        "backends": backends_out,
        "grading_policy": GRADING_POLICY,
        "condensate_strengths": build_strength_summary(backends_out),
    }
    args.output.write_text(json.dumps(final, indent=2), encoding="utf-8")
    print(json.dumps(final["condensate_strengths"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
