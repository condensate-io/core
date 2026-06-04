#!/usr/bin/env python3
"""Render Markdown benchmarks."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from benchmarks.metrics.report import build_strength_summary
from benchmarks.metrics.target_benchmark import (
    TARGET_BENCHMARK_LABEL,
    TARGET_BENCHMARK_PUBLISHED,
    TARGET_BENCHMARK_SHORT,
)


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


def render_report(payload: dict[str, Any]) -> str:
    payload = dict(payload)
    if payload.get("backends"):
        payload["condensate_strengths"] = build_strength_summary(payload["backends"])
    target = TARGET_BENCHMARK_PUBLISHED
    lines: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"# Condensate vs {TARGET_BENCHMARK_LABEL} — LoCoMo Full Run")
    lines.append("")
    lines.append(f"**Generated:** {now}")
    lines.append(f"**Dataset:** `{payload.get('dataset', 'unknown')}`")
    lines.append(f"**Conversations:** {payload.get('samples_evaluated', '?')}")
    lines.append(f"**Scoring:** {payload.get('scoring', 'retrieval + native_answer')}")
    grader = payload.get("grader", {})
    if grader:
        lines.append(f"**LLM grader model:** {grader.get('model', 'none')}")
        if grader.get("estimated_usd_actual") is not None:
            lines.append(f"**LLM grader cost (actual):** ${grader['estimated_usd_actual']:.4f}")
    lines.append("")
    lines.append(f"*{target['source_note']}*")
    lines.append("")

    lines.append("## Executive summary")
    lines.append("")
    strengths = payload.get("condensate_strengths", {})
    lines.append(f"> {strengths.get('headline', '—')}")
    lines.append("")

    lines.append("## LoCoMo metrics (memory systems, not OpenAI-as-answerer)")
    lines.append("")
    lines.append(
        f"| Backend | Retrieval | Native answer | LLM graded | Avg tokens/query | vs {TARGET_BENCHMARK_LABEL} tokens |"
    )
    lines.append(
        "| ------- | --------- | ------------- | ---------- | ---------------- | -------------- |"
    )

    backends = payload.get("backends", {})
    for name, report in backends.items():
        summary = report.get("summary", {})
        retr_acc = summary.get("retrieval_accuracy")
        native_acc = summary.get("native_accuracy")
        graded_acc = summary.get("graded_accuracy")
        tokens = summary.get("avg_retrieved_tokens")
        vs_target = ""
        if tokens and target["locomo_tokens_mean"]:
            ratio = tokens / target["locomo_tokens_mean"]
            vs_target = f"{ratio:.2f}× {TARGET_BENCHMARK_SHORT} mean"
        token_cell = f"{tokens:.0f}" if tokens else "—"
        lines.append(
            f"| **{name}** | {_pct(retr_acc)} | {_pct(native_acc)} | "
            f"{_pct(graded_acc)} | {token_cell} | {vs_target or '—'} |"
        )

    lines.append("")
    lines.append(f"### {TARGET_BENCHMARK_LABEL} (LoCoMo published reference)")
    lines.append("")
    lines.append(f"- Overall QA: **{target['locomo_overall_pct']}%**")
    lines.append(f"- Mean tokens/query: **{target['locomo_tokens_mean']:,}**")
    lines.append(
        f"- Full-context baseline: **~{target['locomo_full_context_tokens']:,}** tokens/query"
    )
    lines.append("")

    condensate = backends.get("condensate", {}).get("summary", {})
    if condensate:
        lines.append("### Condensate native retrieval")
        lines.append("")
        lines.append(f"- Retrieval accuracy: **{_pct(condensate.get('retrieval_accuracy'))}**")
        lines.append(f"- Native answer accuracy: **{_pct(condensate.get('native_accuracy'))}**")
        lines.append(f"- Avg tokens/query: **{condensate.get('avg_retrieved_tokens', 0):.0f}**")
        lines.append("")

    lines.append("## Category breakdown (retrieval accuracy)")
    lines.append("")
    target_cats = target["locomo_categories"]
    all_cats: set[str] = set(target_cats.keys())
    for report in backends.values():
        all_cats.update(report.get("summary", {}).get("by_category", {}).keys())

    header = f"| Category | {TARGET_BENCHMARK_LABEL} | " + " | ".join(backends.keys()) + " |"
    sep = "| -------- | ---------------- | " + " | ".join(["---"] * len(backends)) + " |"
    lines.append(header)
    lines.append(sep)
    for cat in sorted(all_cats):
        target_val = target_cats.get(cat)
        target_cell = f"{target_val}%" if target_val else "—"
        cells = []
        for name in backends:
            bucket = backends[name].get("summary", {}).get("by_category", {}).get(cat)
            cells.append(_pct(bucket.get("accuracy")) if bucket else "—")
        lines.append(f"| {cat} | {target_cell} | " + " | ".join(cells) + " |")

    lines.append("")
    lines.append("## Condensate differentiation")
    lines.append("")
    condensate_summary = condensate or {}
    retr = _pct(condensate_summary.get("retrieval_accuracy"))
    open_dom = condensate_summary.get("by_category", {}).get("open-domain", {})
    open_pct = open_dom.get("accuracy", 0) * 100 if open_dom else 0
    adv = condensate_summary.get("by_category", {}).get("adversarial", {})
    adv_pct = adv.get("accuracy", 0) * 100 if adv else 0
    tok = condensate_summary.get("avg_retrieved_tokens", 0)
    lines.append(
        f"Condensate targets **assertion supersession** (retire contradicted facts) vs add-only "
        f"{TARGET_BENCHMARK_SHORT} memory products. Latest live run: **{retr}** overall retrieval "
        f"at **~{tok:.0f}** tokens/query — open-domain **{open_pct:.1f}%** vs target benchmark "
        f"**{target_cats.get('open-domain', 76)}%**; multi-hop and single-hop remain gaps. "
        f"Adversarial retrieval **{adv_pct:.1f}%** (LOC-013). See "
        f"`benchmarks/docs/COMPETITIVE_POSITIONING.md` for ContradictionBench + LoCoMo narrative."
    )
    lines.append("")
    lines.append(f"| Capability | {TARGET_BENCHMARK_LABEL} class | Condensate |")
    lines.append("| ---------- | ---- | ---------- |")
    lines.append("| Memory updates | ADD-only (no overwrite) | Assertion supersession graph |")
    lines.append("| ContradictionBench | Not published | See separate run (structured 100% vs full 0%) |")
    lines.append("| Provenance / HITL | Limited | First-class assertion provenance |")
    lines.append("")

    if grader:
        lines.append("## LLM grader usage (equivalence only)")
        lines.append("")
        lines.append(f"- Model: `{grader.get('model')}`")
        lines.append(f"- API calls: {grader.get('requests', 0):,}")
        lines.append(f"- Input tokens: {grader.get('input_tokens', 0):,}")
        lines.append(f"- Output tokens: {grader.get('output_tokens', 0):,}")
        if grader.get("estimated_usd_actual") is not None:
            lines.append(f"- Cost: **${grader['estimated_usd_actual']:.4f}** USD")
        lines.append("")

    lines.append("## Methodology notes")
    lines.append("")
    lines.append("- **Retrieval accuracy**: gold answer present in retrieved context (no LLM).")
    lines.append("- **Native answer accuracy**: Condensate `/memory/retrieve` answer vs gold (local fuzzy match).")
    lines.append("- **LLM graded**: optional gpt-4o-mini equivalence on short strings only — never full transcripts.")
    lines.append(
        f"- {TARGET_BENCHMARK_LABEL} overall QA % uses a private answerer stack; compare directionally on retrieval/tokens."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    args.output.write_text(render_report(payload), encoding="utf-8")
    print(f"Wrote {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
