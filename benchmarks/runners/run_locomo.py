"""LoCoMo benchmark runner — multi-backend evaluation with checkpoint/resume."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from benchmarks.backends.condensate import CondensateBackend
from benchmarks.backends.full_context import FullContextBackend
from benchmarks.backends.observations import ObservationsBackend
from benchmarks.backends.registry import build_backend
from benchmarks.backends.structured import StructuredMemoryBackend
from benchmarks.data.locomo_loader import (
    conversation_to_messages,
    full_transcript_tokens_hint,
    get_qa_pairs,
    load_samples,
    resolve_dataset_path,
    sample_observations,
    turn_lookup,
)
from benchmarks.metrics.judge import AnswerGrader
from benchmarks.metrics.qa import score_qa, summarize_qa_results
from benchmarks.metrics.report import build_strength_summary, merge_backend_summary
from benchmarks.metrics.tokens import count_tokens

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
    return [part.strip() for part in spec.split(",") if part.strip()]


def score_row(
    backend_name: str,
    backend: Any,
    session_id: str,
    qa: dict[str, Any],
    turns: dict[str, str],
    grader: AnswerGrader,
    *,
    llm_grade: bool = False,
) -> dict[str, Any]:
    context = backend.search(session_id, qa["question"])
    row = score_qa(context, qa, turns)
    row["retrieved_tokens"] = backend.token_count(context)

    if backend_name == "condensate":
        native = getattr(backend, "last_native_answer", "") or ""
        row["native_answer"] = native
        row["strategy"] = getattr(backend, "last_strategy", "")
        grade = grader.grade(
            qa["question"],
            qa.get("answer"),
            native,
            adversarial=bool(qa.get("adversarial")),
            adversarial_trap=str(qa.get("adversarial_trap", qa.get("answer", ""))),
        )
        row["native_correct"] = grade.correct
        row["native_grading_method"] = grade.grading_method
        if llm_grade and native.strip():
            graded = grader.grade(
                qa["question"],
                qa.get("answer"),
                native,
                adversarial=bool(qa.get("adversarial")),
                adversarial_trap=str(qa.get("adversarial_trap", qa.get("answer", ""))),
            )
            row["graded_correct"] = graded.correct
            row["grading_method"] = graded.grading_method
    return row


def _ingest_sample(backend_name: str, backend: Any, session_id: str, sample: dict[str, Any]) -> float:
    started = time.perf_counter()
    if backend_name == "condensate":
        if os.getenv("CONDENSATE_SKIP_INGEST", "").strip() in ("1", "true", "yes"):
            return (time.perf_counter() - started) * 1000.0
        backend.ingest_sample(session_id, sample)
        if hasattr(backend, "wait_for_condensation"):
            backend.wait_for_condensation(session_id)
        return (time.perf_counter() - started) * 1000.0

    backend.reset(session_id)
    if backend_name == "observations":
        backend.load_observations(session_id, sample_observations(sample))
    elif backend_name == "structured":
        messages = [
            {"role": "system", "content": line, "status": "active"}
            for line in sample_observations(sample)
        ]
        backend.add(session_id, messages)
    else:
        backend.add(session_id, conversation_to_messages(sample["conversation"]))
    return (time.perf_counter() - started) * 1000.0


def run_backend(
    backend_name: str,
    samples: list[dict[str, Any]],
    *,
    resume: bool = False,
    resume_sample_reports: list[dict[str, Any]] | None = None,
    llm_grade: bool = False,
) -> dict[str, Any]:
    backend = build_backend(backend_name)  # type: ignore[arg-type]
    grader = AnswerGrader(use_llm_fallback=llm_grade)
    completed: dict[str, dict[str, Any]] = {}
    if resume and resume_sample_reports:
        for report in resume_sample_reports:
            completed[str(report.get("sample_id"))] = report

    sample_reports: list[dict[str, Any]] = []
    all_qa: list[dict[str, Any]] = []
    token_samples: list[int] = []
    transcript_tokens = 0

    for sample in samples:
        session_id = str(sample["sample_id"])
        if session_id in completed:
            sample_reports.append(completed[session_id])
            all_qa.extend(completed[session_id].get("qa_results", []))
            summary = completed[session_id].get("summary", {})
            if summary.get("avg_retrieved_tokens"):
                token_samples.extend([int(summary["avg_retrieved_tokens"])] * summary.get("total", 1))
            continue

        ingest_ms = _ingest_sample(backend_name, backend, session_id, sample)
        turns = turn_lookup(sample["conversation"])
        qa_results: list[dict[str, Any]] = []
        for qa in get_qa_pairs(sample):
            qa_results.append(
                score_row(
                    backend_name,
                    backend,
                    session_id,
                    qa,
                    turns,
                    grader,
                    llm_grade=llm_grade,
                )
            )
        qa_summary = summarize_qa_results(qa_results)
        transcript_tokens = full_transcript_tokens_hint(sample, count_tokens)
        per_sample_tokens = [r.get("retrieved_tokens", 0) for r in qa_results if r.get("retrieved_tokens")]
        sample_summary = merge_backend_summary(qa_summary, per_sample_tokens, transcript_tokens)
        report = {
            "backend": backend_name,
            "sample_id": session_id,
            "ingest_ms": round(ingest_ms, 2),
            "summary": sample_summary,
            "qa_results": qa_results,
        }
        sample_reports.append(report)
        all_qa.extend(qa_results)
        token_samples.extend(per_sample_tokens)

    overall = summarize_qa_results(all_qa)
    if token_samples and transcript_tokens:
        overall = merge_backend_summary(overall, token_samples, transcript_tokens)
    elif token_samples:
        overall["avg_retrieved_tokens"] = round(sum(token_samples) / len(token_samples), 2)

    return {
        "backend": backend_name,
        "samples": len(sample_reports),
        "summary": overall,
        "sample_reports": sample_reports,
    }


def backend_is_complete(
    report: dict[str, Any],
    backend_name: str,
    samples: list[dict[str, Any]],
) -> bool:
    backend_report = report.get("backends", {}).get(backend_name, {})
    existing = {str(r.get("sample_id")) for r in backend_report.get("sample_reports", [])}
    expected = {str(s["sample_id"]) for s in samples}
    return expected.issubset(existing)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LoCoMo multi-backend benchmark")
    parser.add_argument("--dataset", type=Path, default=None)
    parser.add_argument("--backend", default="all")
    parser.add_argument("--skip-condensate", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--llm-grade", action="store_true")
    args = parser.parse_args()

    dataset_path = resolve_dataset_path(args.dataset)
    samples = load_samples(dataset_path)
    backends = resolve_backends(args.backend, skip_condensate=args.skip_condensate)

    payload: dict[str, Any] = {
        "benchmark": "locomo",
        "harness": "condensate-native",
        "scoring": "retrieval + native_answer + optional_llm_grade",
        "dataset": str(dataset_path),
        "samples_evaluated": len(samples),
        "total_qa_pairs": sum(len(get_qa_pairs(s)) for s in samples),
        "grading_policy": GRADING_POLICY,
        "backends": {},
    }

    if args.resume and args.output.exists():
        try:
            existing = json.loads(args.output.read_text(encoding="utf-8"))
            payload.update({k: v for k, v in existing.items() if k in payload or k == "backends"})
        except json.JSONDecodeError:
            pass

    for name in backends:
        prior = payload.get("backends", {}).get(name, {})
        resume_reports = prior.get("sample_reports") if args.resume else None
        print(f"Running backend: {name}", flush=True)
        payload["backends"][name] = run_backend(
            name,
            samples,
            resume=args.resume,
            resume_sample_reports=resume_reports,
            llm_grade=args.llm_grade,
        )
        if args.output.exists():
            partial = dict(payload)
            partial["condensate_strengths"] = build_strength_summary(partial["backends"])
            args.output.write_text(json.dumps(partial, indent=2), encoding="utf-8")
        print(f"Checkpoint: {name} complete", flush=True)

    payload["condensate_strengths"] = build_strength_summary(payload["backends"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
