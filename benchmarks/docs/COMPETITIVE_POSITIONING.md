# Condensate vs target benchmark — competitive positioning

Numbers below come from LoCoMo-10 run artifacts in `benchmarks/results/` (canonical fair run: `locomo10_condensate_v53_fair.json`, master: `locomo10_full_report.json`).

Published reference scores are tracked as the **target benchmark** (industry LoCoMo memory-system leaderboard).

## LoCoMo-10 headline (condensate v5.3 **fair ingest**, canonical)

Artifact: `benchmarks/results/locomo10_condensate_v53_fair.json` — session-scoped retrieve, fresh ingest per conversation (not QA-only).

| Metric | Condensate v5.3 fair | Target benchmark | Notes |
| ------ | -------------------- | ---------------- | ----- |
| Overall retrieval | **82.0%** | 92.5% | **LOC-015 not met** — see P2/P3 in work tracker |
| Avg tokens/query | **1,749** | 6,956 | |
| Adversarial retrieval | **55.4%** | — | Fair ingest includes raw dialog; compare to v5.2 QA-only 92.8% |
| Temporal | 93.5% | 92.8% | LOC-012 target >90% |
| Multi-hop | 70.8% | 93.3% | LOC-011 target >75% |
| Single-hop | 81.2% | 92.3% | |
| Open-domain | 93.3% | 76.0% | |

Per-conversation retrieval (10/10):

| Conversation | Retrieval |
| ------------ | --------- |
| conv-26 | 77.4% |
| conv-30 | 81.0% |
| conv-41 | 79.3% |
| conv-42 | 79.6% |
| conv-43 | 80.2% |
| conv-44 | 90.5% |
| conv-47 | 76.3% |
| conv-48 | 87.0% |
| conv-49 | 82.7% |
| conv-50 | 87.2% |

Master report: merge via `make test-locomo-report` → `locomo10_full_report.json`.


## LoCoMo-10 headline (condensate v5.2 full, QA-only 2026-05-29)

| Metric | Condensate v5.2 full | conv-26 only | Target benchmark | Notes |
| ------ | -------------------- | ------------ | ---------------- | ----- |
| Overall retrieval | **65.8%** | **89.5%** | 92.5% | Full run QA-only on shared project; fresh per-conv ingest recommended |
| Avg tokens/query | **2,201** | ~694 | 6,956 | Wider context vs v5.1 (921 tok/q) |
| Adversarial retrieval | **92.8%** | 66.0% | — | **LOC-013 done** — adversarial filter |
| Temporal | 73.2% | 100% | 92.8% | LOC-012 |
| Multi-hop | 51.0% | 84.6% | 93.3% | LOC-011 |
| Single-hop | 39.4% | 93.8% | 92.3% | Cross-conv noise on shared project |
| Open-domain | 59.1% | 98.6% | 76.0% | conv-26 beats target; full run diluted |

Master report merged 2026-05-29: `locomo10_full_report.json` ← `locomo10_condensate_v52_full.json`.

## LoCoMo-10 headline (condensate v5.1, prior canonical)

## LoCoMo adversarial retrieval

Adversarial QA checks whether the **trap (wrong) answer** appears in retrieved context. A pass means the trap is **absent** from retrieved text.

| Backend | Adversarial retrieval | Interpretation |
| ------- | --------------------- | -------------- |
| full_context | 40.1% | Trap often present in raw transcript |
| observations | 52.2% | Fact corpus still contains some traps |
| structured | 40.1% | Same as full_context (no supersession on ingest path) |
| condensate (v1 harness) | 96.4% | **Artifact:** benchmark scored UUID `sources`, not text |
| condensate (v5, 2026-05-28) | **62.8%** | Real context scoring; observation boost helps but traps still leak |
| Target benchmark (overall QA) | 92.5% | Uses private answerer; not directly comparable |

**Condensate differentiation:** assertion supersession graph is designed to retire contradicted facts instead of add-only target-benchmark-class accumulation. v5 improves trap filtering via observation prioritization; full supersession at retrieve time is LOC-013.

## ContradictionBench (supersession)

Run via Docker:

```bash
wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && make test-contradiction"
```

| Backend | Role |
| ------- | ---- |
| full_context | Keeps superseded facts in context → fails trap cases |
| structured | Active-assertion-only memory → passes supersession cases |

ContradictionBench is the cleanest proof point for **why Condensate vs add-only memory** on contradiction handling; LoCoMo adversarial category is noisier because traps are embedded in long dialogs.

## Token efficiency vs accuracy (LoCoMo-10)

| Backend | Retrieval | Tokens/query |
| ------- | --------- | ------------ |
| full_context | 80.4% | ~20,476 |
| observations | 69.2% | ~6,307 |
| condensate (v2, 2026-05-27) | 43.5% | ~500 |
| condensate (v5, 2026-05-28) | **73.3%** | **~1,014** |
| Target benchmark | 92.5% | ~6,956 |

**LOC-015 progress:** Under target benchmark token budget at **1,014 tok/q** but retrieval **73.3%** (target >85%). Raising budget toward 2–3K while keeping rerank/heuristic ranking is the next tradeoff to explore.

## v5.2 retrieval changes (2026-05-29)

- **LOC-013 fix:** `should_apply_adversarial_filter()` — no raw-dialog stripping on counterfactual multihop (`would … if …` questions)
- Wider **single-hop recall** supplementary queries (kids, books, activities, camping, LGBTQ events)
- **qa.py:** list-answer matching, temporal day/month/relative heuristics, relationship-status inference
- Rebuilt harness: `run_locomo.py`, `condensate.py` (bulk ingest + context-first retrieve)
- Bench artifact (in progress): `benchmarks/results/locomo10_condensate_v52_sample.json` (conv-26)

## v5.1 retrieval changes (summary)

- Heuristic keyword rerank + wider context budget (35 items, ~28K char cap)
- Observation / session-summary score boosts; temporal multi-query fusion
- Evidence-complete scoring for non-adversarial categories; temporal year inference (`last year` → calendar year)
- Bench artifact: `benchmarks/results/locomo10_condensate_v5_full.json`

## Why Condensate vs target benchmark class (one paragraph)

Add-only memory products lead published LoCoMo numbers using private answer stacks. Condensate optimizes a **provable assertion graph** with supersession, HITL review, and ContradictionBench-validated stale-fact removal. On LoCoMo-10 v5, Condensate **beats the target benchmark on open-domain retrieval** at **~15% of its token cost**, with temporal retrieval approaching transcript baselines. Multi-hop and single-hop remain the focus for closing the overall gap to the target benchmark **92.5%** QA score.
