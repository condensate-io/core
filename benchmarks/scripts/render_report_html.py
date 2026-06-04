#!/usr/bin/env python3
"""Convert LoCoMo benchmark Markdown/CSV reports to styled HTML."""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

TABLE_SEP = re.compile(r"^\|\s*[-:]+\s*\|")
HEADER = re.compile(r"^(#{1,6})\s+(.*)$")
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BOLD = re.compile(r"\*\*([^*]+)\*\*")
CODE = re.compile(r"`([^`]+)`")


def _inline(text: str) -> str:
    text = html.escape(text)
    text = LINK.sub(r'<a href="\2">\1</a>', text)
    text = BOLD.sub(r"<strong>\1</strong>", text)
    text = CODE.sub(r"<code>\1</code>", text)
    return text


def _parse_table(lines: list[str], start: int) -> tuple[str, int]:
    header_cells = [c.strip() for c in lines[start].strip().strip("|").split("|")]
    body_rows: list[list[str]] = []
    idx = start + 2
    while idx < len(lines) and lines[idx].strip().startswith("|"):
        row = [c.strip() for c in lines[idx].strip().strip("|").split("|")]
        body_rows.append(row)
        idx += 1

    thead = "".join(f"<th>{_inline(cell)}</th>" for cell in header_cells)
    tbody_parts: list[str] = []
    for row in body_rows:
        cells = row + [""] * max(0, len(header_cells) - len(row))
        tbody_parts.append(
            "<tr>" + "".join(f"<td>{_inline(cell)}</td>" for cell in cells[: len(header_cells)]) + "</tr>"
        )
    table_html = f"<table><thead><tr>{thead}</tr></thead><tbody>{''.join(tbody_parts)}</tbody></table>"
    return table_html, idx


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    out: list[str] = []
    idx = 0
    in_ul = False
    in_blockquote = False

    def close_lists() -> None:
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False

    def close_blockquote() -> None:
        nonlocal in_blockquote
        if in_blockquote:
            out.append("</blockquote>")
            in_blockquote = False

    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()

        if not stripped:
            close_lists()
            close_blockquote()
            idx += 1
            continue

        header_match = HEADER.match(stripped)
        if header_match:
            close_lists()
            close_blockquote()
            level = len(header_match.group(1))
            out.append(f"<h{level}>{_inline(header_match.group(2))}</h{level}>")
            idx += 1
            continue

        if stripped.startswith("|") and idx + 1 < len(lines) and TABLE_SEP.match(lines[idx + 1].strip()):
            close_lists()
            close_blockquote()
            table_html, idx = _parse_table(lines, idx)
            out.append(table_html)
            continue

        if stripped.startswith(">"):
            close_lists()
            if not in_blockquote:
                out.append("<blockquote>")
                in_blockquote = True
            out.append(f"<p>{_inline(stripped.lstrip('>').strip())}</p>")
            idx += 1
            continue

        if stripped.startswith("- "):
            close_blockquote()
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{_inline(stripped[2:].strip())}</li>")
            idx += 1
            continue

        close_lists()
        close_blockquote()
        out.append(f"<p>{_inline(stripped)}</p>")
        idx += 1

    close_lists()
    close_blockquote()
    return "\n".join(out)


def _accuracy_style(value: str) -> str:
    try:
        pct = float(value)
    except ValueError:
        return ""
    if pct >= 0.8:
        return "acc-high"
    if pct >= 0.5:
        return "acc-mid"
    return "acc-low"


def csv_to_html(csv_path: Path) -> str:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    headers = rows[0].keys() if rows else []
    thead = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body: list[str] = []
    for row in rows:
        cells: list[str] = []
        for key in headers:
            raw = row[key]
            if key == "accuracy":
                cls = _accuracy_style(raw)
                pct = f"{float(raw) * 100:.1f}%"
                cells.append(f'<td class="{cls}">{html.escape(pct)}</td>')
            else:
                cells.append(f"<td>{html.escape(raw)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")

    return f"<table class=\"csv-table\"><thead><tr>{thead}</tr></thead><tbody>{''.join(body)}</tbody></table>"


STYLES = """
:root {
  --bg: #f6f8fa;
  --card: #ffffff;
  --text: #1f2328;
  --muted: #656d76;
  --border: #d0d7de;
  --accent: #0969da;
  --quote-bg: #f0f6ff;
  --acc-high: #dafbe1;
  --acc-mid: #fff8c5;
  --acc-low: #ffebe9;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.55;
}
.wrap {
  max-width: 1100px;
  margin: 0 auto;
  padding: 2rem 1.25rem 3rem;
}
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.75rem 2rem;
  box-shadow: 0 1px 2px rgba(27, 31, 36, 0.06);
}
h1 { font-size: 1.75rem; margin: 0 0 0.75rem; }
h2 { font-size: 1.25rem; margin: 2rem 0 0.75rem; border-bottom: 1px solid var(--border); padding-bottom: 0.35rem; }
h3 { font-size: 1.05rem; margin: 1.5rem 0 0.5rem; color: var(--muted); }
p { margin: 0.5rem 0; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
blockquote {
  margin: 1rem 0;
  padding: 0.85rem 1rem;
  border-left: 4px solid var(--accent);
  background: var(--quote-bg);
  border-radius: 0 8px 8px 0;
}
blockquote p { margin: 0; }
ul { margin: 0.5rem 0 0.75rem 1.25rem; }
code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.92em;
  background: #eef1f4;
  padding: 0.1em 0.35em;
  border-radius: 4px;
}
table {
  width: 100%;
  border-collapse: collapse;
  margin: 0.75rem 0 1.25rem;
  font-size: 0.94rem;
}
th, td {
  border: 1px solid var(--border);
  padding: 0.55rem 0.65rem;
  text-align: left;
  vertical-align: top;
}
th {
  background: #f3f4f6;
  font-weight: 600;
}
tbody tr:nth-child(even) { background: #fafbfc; }
.csv-table td.acc-high { background: var(--acc-high); font-weight: 600; }
.csv-table td.acc-mid { background: var(--acc-mid); }
.csv-table td.acc-low { background: var(--acc-low); font-weight: 600; }
.qa-table tr.hit td:first-child { border-left: 4px solid #1a7f37; }
.qa-table tr.miss td:first-child { border-left: 4px solid #cf222e; }
.qa-table .badge {
  display: inline-block;
  font-size: 0.78rem;
  font-weight: 600;
  padding: 0.12em 0.45em;
  border-radius: 999px;
}
.badge-hit { background: var(--acc-high); color: #1a7f37; }
.badge-miss { background: var(--acc-low); color: #cf222e; }
pre.context {
  margin: 0.35rem 0 0;
  padding: 0.5rem 0.65rem;
  background: #f6f8fa;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.82rem;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 12rem;
  overflow: auto;
}
details summary { cursor: pointer; color: var(--accent); font-size: 0.88rem; }
.meta {
  color: var(--muted);
  font-size: 0.92rem;
  margin-bottom: 1rem;
}
@media (max-width: 720px) {
  .card { padding: 1.25rem; }
  table { font-size: 0.85rem; display: block; overflow-x: auto; }
}
"""


def wrap_page(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>{STYLES}</style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      {body_html}
    </div>
  </div>
</body>
</html>
"""


def render_markdown_file(src: Path, dest: Path) -> None:
    md = src.read_text(encoding="utf-8")
    title_match = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
    title = title_match.group(1) if title_match else src.stem
    body = markdown_to_html(md)
    dest.write_text(wrap_page(title, body), encoding="utf-8")
    print(f"Wrote {dest}", file=sys.stderr)


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


def _summary_table(summary: dict[str, Any]) -> str:
    by_cat = summary.get("by_category") or {}
    rows: list[str] = []
    for category in sorted(by_cat):
        bucket = by_cat[category]
        total = bucket.get("total", 0)
        hits = bucket.get("hits", 0)
        acc = bucket.get("accuracy")
        cls = _accuracy_style(str(acc)) if acc is not None else ""
        rows.append(
            "<tr>"
            f"<td>{html.escape(category)}</td>"
            f"<td>{hits}/{total}</td>"
            f'<td class="{cls}">{_pct(acc)}</td>'
            "<td></td>"
            "</tr>"
        )
    overall_acc = summary.get("retrieval_accuracy")
    overall_cls = _accuracy_style(str(overall_acc)) if overall_acc is not None else ""
    rows.append(
        "<tr><td><strong>Overall</strong></td>"
        f"<td>{summary.get('retrieval_hits', '—')}/{summary.get('total', '—')}</td>"
        f'<td class="{overall_cls}"><strong>{_pct(overall_acc)}</strong></td>'
        f"<td>{summary.get('avg_retrieved_tokens', '—')}</td></tr>"
    )
    return (
        '<table class="csv-table"><thead><tr>'
        "<th>Category</th><th>Hits/Total</th><th>Retrieval</th><th>Avg tokens</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _qa_row(qa: dict[str, Any], index: int) -> str:
    hit = bool(qa.get("retrieval_hit"))
    row_cls = "hit" if hit else "miss"
    badge_cls = "badge-hit" if hit else "badge-miss"
    badge = "HIT" if hit else "MISS"
    gold = qa.get("answer")
    if gold is not None and not isinstance(gold, str):
        gold = str(gold)
    evidence = ", ".join(qa.get("evidence_ids") or []) or "—"
    recall = qa.get("evidence_recall")
    recall_cell = _pct(recall) if isinstance(recall, (int, float)) else "—"
    native = str(qa.get("native_answer") or "").strip()
    context_block = ""
    if native:
        preview = native if len(native) <= 280 else native[:277] + "..."
        context_block = (
            f"<details><summary>Retrieved context ({qa.get('retrieved_tokens', '?')} tok)</summary>"
            f"<pre class=\"context\">{html.escape(native)}</pre></details>"
            if len(native) > 280
            else f"<pre class=\"context\">{html.escape(preview)}</pre>"
        )
    return (
        f"<tr class=\"{row_cls}\">"
        f"<td>{index}</td>"
        f'<td><span class="badge {badge_cls}">{badge}</span></td>'
        f"<td>{html.escape(str(qa.get('category') or '—'))}</td>"
        f"<td>{html.escape(str(qa.get('question') or ''))}</td>"
        f"<td>{html.escape(str(gold or '—'))}</td>"
        f"<td>{html.escape(evidence)}</td>"
        f"<td>{recall_cell}</td>"
        f"<td>{qa.get('retrieved_tokens', '—')}</td>"
        f"<td>{html.escape(str(qa.get('strategy') or '—'))}</td>"
        f"<td>{context_block}</td>"
        "</tr>"
    )


def json_report_to_html(payload: dict[str, Any]) -> str:
    parts: list[str] = ["<h1>LoCoMo QA report</h1>"]
    parts.append(
        f'<p class="meta">Dataset: <code>{html.escape(str(payload.get("dataset", "unknown")))}</code> · '
        f"Conversations: {payload.get('samples_evaluated', '?')} · "
        f"QA pairs: {payload.get('total_qa_pairs', '?')}</p>"
    )
    backends = payload.get("backends") or {}
    for backend_name, report in backends.items():
        summary = report.get("summary") or {}
        parts.append(f"<h2>{html.escape(backend_name)}</h2>")
        parts.append(
            f"<p class=\"meta\">Retrieval {_pct(summary.get('retrieval_accuracy'))} · "
            f"Native {_pct(summary.get('native_accuracy'))} · "
            f"Avg {summary.get('avg_retrieved_tokens', '—')} tokens/query · "
            f"Savings vs transcript {_pct(summary.get('token_savings_vs_transcript'))}</p>"
        )
        parts.append(_summary_table(summary))
        for sample in report.get("sample_reports") or []:
            sample_id = sample.get("sample_id", "unknown")
            ingest_ms = sample.get("ingest_ms")
            ingest_note = f" · ingest {ingest_ms:.0f} ms" if isinstance(ingest_ms, (int, float)) else ""
            parts.append(f"<h3>{html.escape(str(sample_id))}{ingest_note}</h3>")
            qa_results = sample.get("qa_results") or []
            rows = "".join(_qa_row(qa, i + 1) for i, qa in enumerate(qa_results))
            parts.append(
                '<table class="qa-table"><thead><tr>'
                "<th>#</th><th>Result</th><th>Category</th><th>Question</th><th>Gold</th>"
                "<th>Evidence</th><th>Recall</th><th>Tokens</th><th>Strategy</th><th>Context</th>"
                "</tr></thead><tbody>"
                + rows
                + "</tbody></table>"
            )
    return "\n".join(parts)


def render_json_report_file(src: Path, dest: Path) -> None:
    payload = json.loads(src.read_text(encoding="utf-8"))
    title = f"LoCoMo QA — {src.stem}"
    body = json_report_to_html(payload)
    dest.write_text(wrap_page(title, body), encoding="utf-8")
    print(f"Wrote {dest}", file=sys.stderr)


def render_csv_file(src: Path, dest: Path) -> None:
    title = "LoCoMo misses by category"
    intro = (
        "<h1>LoCoMo misses by category</h1>"
        "<p class=\"meta\">Retrieval miss counts and accuracy by QA category and backend.</p>"
    )
    body = intro + csv_to_html(src)
    dest.write_text(wrap_page(title, body), encoding="utf-8")
    print(f"Wrote {dest}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render benchmark reports as HTML")
    parser.add_argument(
        "--input-json",
        type=Path,
        default=None,
        help="LoCoMo benchmark JSON report (writes QA detail HTML)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output HTML path for --input-json (default: same stem as input)",
    )
    parser.add_argument("--comparative-md", type=Path, default=None)
    parser.add_argument("--failure-md", type=Path, default=None)
    parser.add_argument("--misses-csv", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("benchmarks/results"))
    args = parser.parse_args()

    if args.input_json:
        dest = args.output or args.input_json.with_suffix(".html")
        dest.parent.mkdir(parents=True, exist_ok=True)
        render_json_report_file(args.input_json, dest)
        return 0

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    root = Path(__file__).resolve().parents[2] / "benchmarks" / "results"
    comparative = args.comparative_md or root / "locomo10_comparative_report.md"
    failure = args.failure_md or root / "locomo10_failure_analysis.md"
    misses = args.misses_csv or root / "locomo10_misses_by_category.csv"

    render_markdown_file(comparative, out / "locomo10_comparative_report.html")
    render_markdown_file(failure, out / "locomo10_failure_analysis.html")
    render_csv_file(misses, out / "locomo10_misses_by_category.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
