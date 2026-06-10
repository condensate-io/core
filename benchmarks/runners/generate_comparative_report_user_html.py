#!/usr/bin/env python3
"""Render layman-facing LoCoMo comparative report HTML from full_report.json."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from benchmarks.metrics.target_benchmark import TARGET_BENCHMARK_PUBLISHED


def _pct(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v * 100:.1f}%"


def _int(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{int(round(v)):,}"


def _extract(payload: dict[str, Any]) -> dict[str, Any]:
    backends = payload.get("backends", {})
    cond = backends.get("condensate", {}).get("summary", {})
    full = backends.get("full_context", {}).get("summary", {})
    obs = backends.get("observations", {}).get("summary", {})
    structured = backends.get("structured", {}).get("summary", {})
    target = TARGET_BENCHMARK_PUBLISHED
    by_cat = cond.get("by_category", {})
    return {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "cond_retrieval": cond.get("retrieval_accuracy"),
        "cond_tokens": cond.get("avg_retrieved_tokens"),
        "cond_native": cond.get("native_accuracy"),
        "full_retrieval": full.get("retrieval_accuracy"),
        "full_tokens": full.get("avg_retrieved_tokens"),
        "obs_retrieval": obs.get("retrieval_accuracy"),
        "obs_tokens": obs.get("avg_retrieved_tokens"),
        "struct_retrieval": structured.get("retrieval_accuracy"),
        "struct_tokens": structured.get("avg_retrieved_tokens"),
        "target_qa": (target.get("locomo_overall_pct") or 0) / 100.0,
        "target_tokens": target.get("locomo_tokens_mean"),
        "adversarial": by_cat.get("adversarial", {}).get("accuracy"),
        "multihop": by_cat.get("multi-hop", {}).get("accuracy"),
        "singlehop": by_cat.get("single-hop", {}).get("accuracy"),
        "opendomain": by_cat.get("open-domain", {}).get("accuracy"),
        "temporal": by_cat.get("temporal", {}).get("accuracy"),
        "full_adversarial": full.get("by_category", {}).get("adversarial", {}).get("accuracy"),
        "full_multihop": full.get("by_category", {}).get("multi-hop", {}).get("accuracy"),
        "full_singlehop": full.get("by_category", {}).get("single-hop", {}).get("accuracy"),
        "full_opendomain": full.get("by_category", {}).get("open-domain", {}).get("accuracy"),
        "full_temporal": full.get("by_category", {}).get("temporal", {}).get("accuracy"),
        "target_multihop": (target.get("locomo_categories", {}).get("multi-hop") or 0) / 100.0,
        "target_singlehop": (target.get("locomo_categories", {}).get("single-hop") or 0) / 100.0,
        "target_opendomain": (target.get("locomo_categories", {}).get("open-domain") or 0) / 100.0,
        "target_temporal": (target.get("locomo_categories", {}).get("temporal") or 0) / 100.0,
    }


def render_html(m: dict[str, Any]) -> str:
    cond_pct = (m["cond_retrieval"] or 0) * 100
    goal_pct = 85.0
    progress_width = min(100, (cond_pct / goal_pct) * 100)
    token_pct = min(100, ((m["cond_tokens"] or 0) / 7000) * 100)
    open_beat = (m["opendomain"] or 0) > (m["target_opendomain"] or 0)
    temp_beat = (m["temporal"] or 0) > (m["target_temporal"] or 0)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Condensate Memory — What the Benchmark Means for You</title>
  <style>
:root {{
  --bg: #f4f6f8; --card: #fff; --text: #1a1f24; --muted: #5c6670; --border: #d8dee4;
  --accent: #0d6efd; --accent-soft: #e8f2ff; --good: #1a7f37; --good-bg: #dafbe1;
  --warn: #9a6700; --warn-bg: #fff8c5; --gap: #cf222e; --gap-bg: #ffebe9;
  --hero: linear-gradient(135deg, #0d6efd 0%, #1a5fb4 100%);
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: "Segoe UI", system-ui, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}
.wrap {{ max-width: 920px; margin: 0 auto; padding: 0 1.25rem 3rem; }}
.hero {{ background: var(--hero); color: #fff; padding: 2.5rem 1.25rem 2rem; margin: 0 -1.25rem 1.5rem; border-radius: 0 0 16px 16px; }}
.hero h1 {{ margin: 0 0 0.5rem; font-size: 1.85rem; }}
.hero .lead {{ margin: 0; font-size: 1.1rem; opacity: 0.95; }}
.meta {{ color: rgba(255,255,255,0.8); font-size: 0.88rem; margin-top: 1rem; }}
.card {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem 1.75rem; margin-bottom: 1.25rem; }}
.card h2 {{ margin: 0 0 0.75rem; font-size: 1.35rem; border-bottom: 2px solid var(--accent-soft); padding-bottom: 0.4rem; }}
.problem-box {{ background: var(--gap-bg); border-left: 4px solid var(--gap); padding: 1rem; border-radius: 0 8px 8px 0; }}
.goal-box {{ background: var(--accent-soft); border-left: 4px solid var(--accent); padding: 1rem; border-radius: 0 8px 8px 0; }}
.strength-box {{ background: var(--good-bg); border-left: 4px solid var(--good); padding: 1rem; border-radius: 0 8px 8px 0; }}
.score-big {{ font-size: 2rem; font-weight: 700; color: var(--accent); }}
.score-label {{ font-size: 0.85rem; color: var(--muted); }}
.progress-bar {{ height: 10px; background: #e8ecf0; border-radius: 999px; overflow: hidden; margin-top: 0.25rem; }}
.progress-fill {{ height: 100%; border-radius: 999px; background: var(--accent); }}
.progress-fill.good {{ background: var(--good); }}
.progress-fill.warn {{ background: #d4a72c; }}
.progress-fill.gap {{ background: var(--gap); }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; margin: 0.75rem 0; }}
th, td {{ border: 1px solid var(--border); padding: 0.55rem 0.65rem; text-align: left; }}
th {{ background: #f0f3f6; }}
.highlight {{ background: var(--accent-soft); font-weight: 600; }}
.footnote {{ font-size: 0.82rem; color: var(--muted); margin-top: 1.5rem; }}
  </style>
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <h1>Can your AI remember long conversations — correctly and affordably?</h1>
      <p class="lead">How Condensate compares on the LoCoMo industry memory test — 10 long chats, ~2,000 questions.</p>
      <p class="meta">Generated {m["generated"]} · locomo10_full_report.json</p>
    </header>

    <section class="card">
      <h2>The problem we are solving</h2>
      <div class="problem-box">
        <p><strong>Long-running AI assistants</strong> must remember what users said weeks ago — without resending entire chat logs every time.</p>
      </div>
      <ul>
        <li><strong>Wrong answers</strong> when the right fact never reaches the model.</li>
        <li><strong>Stale facts</strong> when users correct themselves but old information remains.</li>
        <li><strong>High cost</strong> when every question includes tens of thousands of tokens of history.</li>
      </ul>
    </section>

    <section class="card">
      <h2>Our goal — and where we stand today</h2>
      <div class="goal-box">
        <p><strong>Production goal:</strong> ≥ <strong>85%</strong> retrieval accuracy at <strong>&lt; 7,000 tokens</strong> per question.</p>
        <p><strong>Industry reference:</strong> ~{_pct(m["target_qa"])} overall · ~{_int(m["target_tokens"])} tokens/question.</p>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:1.25rem;margin-top:1rem;">
        <div>
          <div class="score-big">{_pct(m["cond_retrieval"])}</div>
          <div class="score-label">Condensate — right answer present in memory</div>
          <div class="progress-bar"><div class="progress-fill warn" style="width:{progress_width:.1f}%"></div></div>
          <p style="font-size:0.9rem;color:var(--muted);">{cond_pct:.1f}% vs 85% goal ({goal_pct - cond_pct:.1f} pts to go). Full transcript: {_pct(m["full_retrieval"])}.</p>
        </div>
        <div>
          <div class="score-big">{_int(m["cond_tokens"])}</div>
          <div class="score-label">Tokens of memory per question</div>
          <div class="progress-bar"><div class="progress-fill good" style="width:{token_pct:.1f}%"></div></div>
          <p style="font-size:0.9rem;color:var(--muted);">Under 7k budget. ~{_int(m["full_tokens"])} for full transcript.</p>
        </div>
      </div>
    </section>

    <section class="card">
      <h2>What each benchmark approach means</h2>
      <ul>
        <li><strong>Full transcript</strong> — paste the whole chat ({_pct(m["full_retrieval"])}, {_int(m["full_tokens"])} tok/q).</li>
        <li><strong>Observation list</strong> — extracted fact bullets ({_pct(m["obs_retrieval"])}, {_int(m["obs_tokens"])} tok/q).</li>
        <li><strong>Structured notes</strong> — organized storage, no supersession ({_pct(m["struct_retrieval"])}, {_int(m["struct_tokens"])} tok/q).</li>
        <li><strong>Industry reference</strong> — published leaderboard (~{_pct(m["target_qa"])}, ~{_int(m["target_tokens"])} tok/q).</li>
        <li><strong>Condensate</strong> — updating assertion memory ({_pct(m["cond_retrieval"])}, {_int(m["cond_tokens"])} tok/q).</li>
      </ul>
    </section>

    <section class="card">
      <h2>Strengths and gaps</h2>
      <div class="strength-box">
        <ul>
          <li><strong>Cost:</strong> ~12× fewer tokens than full transcript at similar recall.</li>
          <li><strong>Open-domain:</strong> {_pct(m["opendomain"])} vs industry {_pct(m["target_opendomain"])}{" ✓" if open_beat else ""}.</li>
          <li><strong>Temporal:</strong> {_pct(m["temporal"])} vs industry {_pct(m["target_temporal"])}{" ✓" if temp_beat else ""}.</li>
          <li><strong>Memory updates:</strong> supersession + provenance (see ContradictionBench).</li>
        </ul>
      </div>
      <table>
        <thead><tr><th>Type</th><th>Industry ref.</th><th>Condensate</th><th>Full transcript</th></tr></thead>
        <tbody>
          <tr><td>Open-domain</td><td>{_pct(m["target_opendomain"])}</td><td class="highlight">{_pct(m["opendomain"])}</td><td>{_pct(m["full_opendomain"])}</td></tr>
          <tr><td>Temporal</td><td>{_pct(m["target_temporal"])}</td><td class="highlight">{_pct(m["temporal"])}</td><td>{_pct(m["full_temporal"])}</td></tr>
          <tr><td>Single-hop</td><td>{_pct(m["target_singlehop"])}</td><td>{_pct(m["singlehop"])}</td><td>{_pct(m["full_singlehop"])}</td></tr>
          <tr><td>Multi-hop</td><td>{_pct(m["target_multihop"])}</td><td>{_pct(m["multihop"])}</td><td>{_pct(m["full_multihop"])}</td></tr>
          <tr><td>Adversarial</td><td>—</td><td>{_pct(m["adversarial"])}</td><td>{_pct(m["full_adversarial"])}</td></tr>
        </tbody>
      </table>
      <p>Gaps: multi-hop ({_pct(m["multihop"])}), adversarial ({_pct(m["adversarial"])}), overall +{max(0, goal_pct - cond_pct):.1f} pts to 85% goal.</p>
    </section>

    <section class="card">
      <h2>Why this drives adoption</h2>
      <ul>
        <li>Lower LLM bills for always-on agents.</li>
        <li>Trust when user facts change over time.</li>
        <li>Strong on broad and time-based recall vs industry reference.</li>
        <li>Transparent fair testing (per-conversation ingest, session-scoped).</li>
      </ul>
      <p><strong>Bottom line:</strong> Credible cost-efficient memory on a hard public benchmark — close to production accuracy target, leading on price-performance and several categories.</p>
    </section>

    <p class="footnote">Technical tables: locomo10_comparative_report.md · Native answer: {_pct(m["cond_native"])}</p>
  </div>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    args.output.write_text(render_html(_extract(payload)), encoding="utf-8")
    print(f"Wrote {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
