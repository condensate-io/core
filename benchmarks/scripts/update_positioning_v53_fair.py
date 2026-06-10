#!/usr/bin/env python3
"""Update COMPETITIVE_POSITIONING.md with v5.3 fair ingest LoCoMo headline."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def _pct(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v * 100:.1f}%"


def _tok(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{int(round(v)):,}"


def extract_headline(payload: dict[str, Any]) -> dict[str, Any]:
    cond = payload.get("backends", {}).get("condensate", {})
    summary = cond.get("summary", {})
    by_cat = summary.get("by_category", {})
    per_conv: list[tuple[str, float]] = []
    for sr in cond.get("sample_reports", []):
        sid = sr.get("sample_id", "?")
        acc = sr.get("summary", {}).get("retrieval_accuracy")
        if acc is not None:
            per_conv.append((sid, acc))
    return {
        "overall_retrieval": summary.get("retrieval_accuracy"),
        "tokens": summary.get("avg_retrieved_tokens"),
        "temporal": by_cat.get("temporal", {}).get("accuracy"),
        "multihop": by_cat.get("multi-hop", {}).get("accuracy"),
        "singlehop": by_cat.get("single-hop", {}).get("accuracy"),
        "opendomain": by_cat.get("open-domain", {}).get("accuracy"),
        "adversarial": by_cat.get("adversarial", {}).get("accuracy"),
        "samples": len(cond.get("sample_reports", [])),
        "per_conv": per_conv,
    }


def render_section(h: dict[str, Any], artifact: str) -> str:
    loc015_pass = (
        h.get("overall_retrieval") is not None
        and h.get("tokens") is not None
        and h["overall_retrieval"] >= 0.85
        and h["tokens"] < 7000
    )
    p1_note = (
        "**LOC-015 met** (≥85% retrieval, <7k tokens/query)"
        if loc015_pass
        else "**LOC-015 not met** — see P2/P3 in work tracker"
    )
    conv_rows = "\n".join(
        f"| {sid} | {_pct(acc)} |" for sid, acc in sorted(h["per_conv"], key=lambda x: x[0])
    )
    return f"""## LoCoMo-10 headline (condensate v5.3 **fair ingest**, canonical)

Artifact: `{artifact}` — session-scoped retrieve, fresh ingest per conversation (not QA-only).

| Metric | Condensate v5.3 fair | Target benchmark | Notes |
| ------ | -------------------- | ---------------- | ----- |
| Overall retrieval | **{_pct(h.get('overall_retrieval'))}** | 92.5% | {p1_note} |
| Avg tokens/query | **{_tok(h.get('tokens'))}** | 6,956 | |
| Adversarial retrieval | **{_pct(h.get('adversarial'))}** | — | Fair ingest includes raw dialog; compare to v5.2 QA-only 92.8% |
| Temporal | {_pct(h.get('temporal'))} | 92.8% | LOC-012 target >90% |
| Multi-hop | {_pct(h.get('multihop'))} | 93.3% | LOC-011 target >75% |
| Single-hop | {_pct(h.get('singlehop'))} | 92.3% | |
| Open-domain | {_pct(h.get('opendomain'))} | 76.0% | |

Per-conversation retrieval ({h['samples']}/10):

| Conversation | Retrieval |
| ------------ | --------- |
{conv_rows}

Master report: merge via `make test-locomo-report` → `locomo10_full_report.json`.

"""


def update_positioning(path: Path, section: str) -> None:
    text = path.read_text(encoding="utf-8")
    marker_old = "## LoCoMo-10 headline (condensate v5.3 **fair ingest**"
    marker_v52 = "## LoCoMo-10 headline (condensate v5.2 full"
    # Replace existing v5.3 fair section if present
    pattern = re.compile(
        r"## LoCoMo-10 headline \(condensate v5\.3 \*\*fair ingest\*\*.*?(?=\n## |\Z)",
        re.DOTALL,
    )
    if pattern.search(text):
        text = pattern.sub(section.rstrip() + "\n\n", text)
    else:
        # Insert before v5.2 section
        insert_at = text.find(marker_v52)
        if insert_at == -1:
            insert_at = text.find("## LoCoMo adversarial")
        if insert_at == -1:
            text = text.rstrip() + "\n\n" + section
        else:
            text = text[:insert_at] + section + text[insert_at:]
    # Update intro line
    intro = (
        "Numbers below come from LoCoMo-10 run artifacts in `benchmarks/results/` "
        "(canonical fair run: `locomo10_condensate_v53_fair.json`, master: `locomo10_full_report.json`)."
    )
    text = re.sub(
        r"Numbers below come from LoCoMo-10 run artifacts in `benchmarks/results/`.*?\n",
        intro + "\n",
        text,
        count=1,
    )
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--positioning", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    h = extract_headline(payload)
    if h["samples"] < 10:
        raise SystemExit(f"Expected 10 conversations, got {h['samples']}")
    section = render_section(h, args.input.as_posix().replace("\\", "/"))
    update_positioning(args.positioning, section)
    print(f"Updated {args.positioning}")
    print(f"Overall: {_pct(h.get('overall_retrieval'))} @ {_tok(h.get('tokens'))} tok/q")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
