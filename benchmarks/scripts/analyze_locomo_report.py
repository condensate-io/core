#!/usr/bin/env python3
"""Failure-mode and efficiency analysis for LoCoMo benchmark reports."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


def _miss_stats_for_backend(backend_report: dict[str, Any]) -> dict[str, dict[str, int]]:
    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "misses": 0})
    for sample in backend_report.get("sample_reports", []):
        for qa in sample.get("qa_results", []):
            category = str(qa.get("category") or "unknown")
            stats[category]["total"] += 1
            if not qa.get("retrieval_hit"):
                stats[category]["misses"] += 1
    return dict(stats)


def _example_misses_for_backend(
    backend_report: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    examples: dict[str, dict[str, Any]] = {}
    for sample in backend_report.get("sample_reports", []):
        sample_id = str(sample.get("sample_id", "unknown"))
        for qa in sample.get("qa_results", []):
            if qa.get("retrieval_hit"):
                continue
            category = str(qa.get("category") or "unknown")
            if category in examples:
                continue
            examples[category] = {
                "sample_id": sample_id,
                "question": qa.get("question"),
                "gold_answer": qa.get("answer"),
                "native_answer": qa.get("native_answer"),
                "evidence_ids": qa.get("evidence_ids", []),
                "retrieved_tokens": qa.get("retrieved_tokens"),
                "evidence_recall": qa.get("evidence_recall"),
            }
    return examples


def _token_efficiency_for_backend(
    backend_report: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sample in backend_report.get("sample_reports", []):
        summary = sample.get("summary", {})
        rows.append(
            {
                "sample_id": sample.get("sample_id"),
                "ingest_ms": sample.get("ingest_ms"),
                "qa_total": summary.get("total"),
                "retrieval_accuracy": summary.get("retrieval_accuracy"),
                "avg_retrieved_tokens": summary.get("avg_retrieved_tokens"),
                "avg_transcript_tokens": summary.get("avg_transcript_tokens"),
                "token_savings_vs_transcript": summary.get("token_savings_vs_transcript"),
            }
        )
    return rows


def _collect_misses_for_category(
    backend_report: dict[str, Any],
    category: str,
) -> list[dict[str, Any]]:
    misses: list[dict[str, Any]] = []
    for sample in backend_report.get("sample_reports", []):
        sample_id = str(sample.get("sample_id", "unknown"))
        for qa in sample.get("qa_results", []):
            if qa.get("retrieval_hit"):
                continue
            if str(qa.get("category") or "unknown") != category:
                continue
            misses.append(
                {
                    "sample_id": sample_id,
                    "question": qa.get("question"),
                    "gold_answer": qa.get("answer"),
                    "native_answer": qa.get("native_answer"),
                    "evidence_ids": qa.get("evidence_ids", []),
                    "evidence_recall": qa.get("evidence_recall"),
                    "retrieved_tokens": qa.get("retrieved_tokens"),
                }
            )
    return misses


def _top_priority_misses(
    payload: dict[str, Any],
    *,
    backend: str = "condensate",
    limit: int = 12,
) -> dict[str, list[dict[str, Any]]]:
    """Rank retrieval misses for LOC-011/019 follow-up (multi-hop + single-hop first)."""
    report = payload.get("backends", {}).get(backend, {})
    ranked: dict[str, list[dict[str, Any]]] = {}
    for category in ("multi-hop", "single-hop"):
        misses = _collect_misses_for_category(report, category)
        misses.sort(
            key=lambda row: (
                float(row.get("evidence_recall") or 0.0),
                -int(row.get("retrieved_tokens") or 0),
            ),
        )
        ranked[category] = misses[:limit]
    return ranked


def analyze_report(payload: dict[str, Any]) -> dict[str, Any]:
    backends = payload.get("backends", {})
    misses_by_backend: dict[str, dict[str, dict[str, int]]] = {}
    example_misses_by_backend: dict[str, dict[str, dict[str, Any]]] = {}
    token_efficiency_by_backend: dict[str, list[dict[str, Any]]] = {}

    for name, report in backends.items():
        misses_by_backend[name] = _miss_stats_for_backend(report)
        example_misses_by_backend[name] = _example_misses_for_backend(report)
        token_efficiency_by_backend[name] = _token_efficiency_for_backend(report)

    return {
        "dataset": payload.get("dataset"),
        "samples_evaluated": payload.get("samples_evaluated"),
        "total_qa_pairs": payload.get("total_qa_pairs"),
        "misses_by_category": misses_by_backend,
        "example_misses": example_misses_by_backend,
        "token_efficiency_by_conversation": token_efficiency_by_backend,
        "priority_misses": _top_priority_misses(payload),
    }


def _pct(hits: int, total: int) -> str:
    if total <= 0:
        return "—"
    return f"{100.0 * hits / total:.1f}%"


def render_markdown(analysis: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# LoCoMo failure-mode analysis")
    lines.append("")
    lines.append(f"**Dataset:** `{analysis.get('dataset', 'unknown')}`")
    lines.append(f"**Conversations:** {analysis.get('samples_evaluated', '?')}")
    lines.append(f"**QA pairs:** {analysis.get('total_qa_pairs', '?')}")
    lines.append("")

    backends = list(analysis.get("misses_by_category", {}).keys())
    if not backends:
        lines.append("No backend results found.")
        return "\n".join(lines)

    lines.append("## Miss counts by category (retrieval)")
    lines.append("")
    all_categories: set[str] = set()
    for backend_stats in analysis["misses_by_category"].values():
        all_categories.update(backend_stats.keys())

    header = "| Category | " + " | ".join(f"{b} misses/total" for b in backends) + " |"
    sep = "| -------- | " + " | ".join(["---"] * len(backends)) + " |"
    lines.append(header)
    lines.append(sep)
    for category in sorted(all_categories):
        cells: list[str] = []
        for backend in backends:
            bucket = analysis["misses_by_category"][backend].get(category, {"total": 0, "misses": 0})
            total = bucket["total"]
            misses = bucket["misses"]
            hits = total - misses
            cells.append(f"{misses}/{total} ({_pct(hits, total)})")
        lines.append(f"| {category} | " + " | ".join(cells) + " |")

    lines.append("")
    lines.append("## Example misses (one per category per backend)")
    lines.append("")
    for backend in backends:
        lines.append(f"### {backend}")
        lines.append("")
        examples = analysis["example_misses"].get(backend, {})
        if not examples:
            lines.append("_No misses recorded._")
            lines.append("")
            continue
        for category in sorted(examples):
            ex = examples[category]
            lines.append(f"**{category}** (`{ex.get('sample_id')}`)")
            lines.append(f"- Question: {ex.get('question')}")
            lines.append(f"- Gold: {ex.get('gold_answer')}")
            if ex.get("native_answer"):
                native = str(ex["native_answer"])
                if len(native) > 240:
                    native = native[:237] + "..."
                lines.append(f"- Native answer: {native}")
            lines.append(f"- Evidence IDs: {', '.join(ex.get('evidence_ids') or []) or '—'}")
            lines.append(f"- Retrieved tokens: {ex.get('retrieved_tokens', '—')}")
            lines.append("")

    priority = analysis.get("priority_misses") or {}
    if priority:
        lines.append("## Priority retrieval misses (condensate — multi-hop & single-hop)")
        lines.append("")
        lines.append(
            "Tagged for LOC-011 / LOC-019: lowest evidence recall first, then highest token use."
        )
        lines.append("")
        for category in ("multi-hop", "single-hop"):
            rows = priority.get(category) or []
            lines.append(f"### {category} ({len(rows)} shown)")
            lines.append("")
            if not rows:
                lines.append("_No misses in this category._")
                lines.append("")
                continue
            for idx, row in enumerate(rows, start=1):
                lines.append(
                    f"{idx}. **{row.get('sample_id')}** — evidence_recall={row.get('evidence_recall', '—')}, "
                    f"tokens={row.get('retrieved_tokens', '—')}"
                )
                lines.append(f"   - Q: {row.get('question')}")
                lines.append(f"   - Gold: {row.get('gold_answer')}")
                lines.append(f"   - Evidence: {', '.join(row.get('evidence_ids') or []) or '—'}")
                lines.append("")

    lines.append("## Token efficiency by conversation")
    lines.append("")
    for backend in backends:
        lines.append(f"### {backend}")
        lines.append("")
        lines.append(
            "| Conversation | Ingest (ms) | Retrieval acc | Avg retrieved tok | Transcript tok | Savings |"
        )
        lines.append(
            "| ------------ | ----------- | ------------- | ----------------- | -------------- | ------- |"
        )
        for row in analysis["token_efficiency_by_conversation"].get(backend, []):
            acc = row.get("retrieval_accuracy")
            acc_cell = f"{acc * 100:.1f}%" if isinstance(acc, (int, float)) else "—"
            savings = row.get("token_savings_vs_transcript")
            savings_cell = f"{savings * 100:.1f}%" if isinstance(savings, (int, float)) else "—"
            lines.append(
                f"| {row.get('sample_id')} | {row.get('ingest_ms', '—')} | {acc_cell} | "
                f"{row.get('avg_retrieved_tokens', '—')} | {row.get('avg_transcript_tokens', '—')} | "
                f"{savings_cell} |"
            )
        lines.append("")

    return "\n".join(lines)


def write_csv(analysis: dict[str, Any], path: Path) -> None:
    backends = list(analysis.get("misses_by_category", {}).keys())
    all_categories: set[str] = set()
    for backend_stats in analysis["misses_by_category"].values():
        all_categories.update(backend_stats.keys())

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["category", "backend", "total", "misses", "hits", "accuracy"])
        for category in sorted(all_categories):
            for backend in backends:
                bucket = analysis["misses_by_category"][backend].get(
                    category, {"total": 0, "misses": 0}
                )
                total = bucket["total"]
                misses = bucket["misses"]
                hits = total - misses
                accuracy = round(hits / total, 4) if total else ""
                writer.writerow([category, backend, total, misses, hits, accuracy])


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze LoCoMo benchmark JSON reports")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None, help="Markdown output path")
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Optional CSV export of miss counts (default: <input_dir>/locomo10_misses_by_category.csv)",
    )
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    analysis = analyze_report(payload)
    markdown = render_markdown(analysis)

    output = args.output or (args.input.parent / "locomo10_failure_analysis.md")
    output.write_text(markdown, encoding="utf-8")
    print(f"Wrote {output}", flush=True)

    csv_path = args.csv or (args.input.parent / "locomo10_misses_by_category.csv")
    write_csv(analysis, csv_path)
    print(f"Wrote {csv_path}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
