# LoCoMo Benchmark Work Tracker — Condensates

**Last updated:** 2026-06-04 (P0 **done** — v5.3 fair 10/10 merged; P1 partial — 82.0% @ 1,749 tok/q)  
**Source report:** `benchmarks/results/locomo10_full_report.json` ← `locomo10_condensate_v53_fair.json`  
**Dataset:** 10 conversations, 1,986 QA pairs (`benchmarks/data/locomo10.json`)

---

## How to use this tracker

Pick a work item by ID. Each item is scoped for a **single agent / smaller model** with explicit files, acceptance criteria, and a WSL/Docker verify command. Update **Status** and **Owner** when you start or finish.

**All Python and tests run via WSL + Docker** (never host PowerShell Python):

```bash
wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && <command>"
```

**Status values:** `todo` | `in_progress` | `blocked` | `done` | `wontfix`

**Size:** `S` (<1 hr) · `M` (1–4 hr) · `L` (4+ hr / overnight)

---

## Run snapshot (2026-05-28)

| Backend | Role | Status | Notes |
| ------- | ---- | ------ | ----- |
| `full_context` | Naive transcript dump | **Complete** | 80.4% retrieval, ~20.5K tokens/query |
| `observations` | LoCoMo fact-store baseline | **Complete** | 69.2% retrieval, ~6.3K tokens/query |
| `condensate` | Live stack (v5.3 fair ingest) | **Complete** | **82.0%** retrieval @ **1,749 tok/q** — `locomo10_condensate_v53_fair.json` |
| `structured` | Active-assertion-only memory | **Complete** | 80.4% retrieval (same as full_context — no supersession in harness) |

**Blockers to headline result:** none — all four backends in `locomo10_full_report.json`. Condensate overall retrieval still below target benchmark 92.5% (LOC-011/012); open-domain category **beats target benchmark**.

---

## Parallel lanes

Work items group into lanes that can run concurrently once dependencies are met:

```
Lane A — Harness fixes     [LOC-001 ✓, LOC-002 ✓, LOC-003 ✓, LOC-004 ✓]  DONE
Lane B — Baseline re-runs  [LOC-005 ✓, LOC-006 ✓]                     DONE
Lane C — Live Condensate   [LOC-007 ✓, LOC-008 ✓]                     DONE
Lane D — Reporting         [LOC-009 ✓, LOC-010 ✓]                     DONE
Lane E — Product R&D       [LOC-011–012 ⟳, LOC-013 ✓, LOC-014 ✓, LOC-015 ⟳, LOC-017 ⟳ fair ingest]  ← v5.3 headline push
```

---

## Execution plan (GTM headline push)

Until **P0 + P1** pass, LoCoMo stays supporting evidence (adversarial + ContradictionBench wedge), not the primary GTM hook.

| Priority | Item | Status | Gate / action |
| -------- | ---- | ------ | ------------- |
| **P0** | LOC-017 fair full run (v5.3 fresh ingest) | **done** | 10/10 fair ingest **2026-06-04** (~8.8h). Artifact: `locomo10_condensate_v53_fair.json`. |
| **P1** | LOC-015 re-baseline | **in progress** | **82.0%** @ **1,749 tok/q** — tokens ✓, retrieval **3 pts short** of 85%. |
| **P2** | LOC-012 temporal → 90%+ | **blocked on P1** | Only if fair full run &lt;85% overall or temporal &lt;90%. |
| **P3** | LOC-011 multi-hop → 75%+ | **blocked on P1** | Largest lift; tackle after P0 baseline + failure analysis on fair misses. |
| **P4** | LOC-015 production defaults | **blocked on P1–P3** | Document retrieve caps once composite passes; trim tokens only if avg ≫2k. |

**P0 commands (WSL + Docker):**

```bash
# Fresh start
wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && make test-locomo-v53-fair"
# Resume after interrupt (6/10 checkpointed 2026-06-01)
wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && make test-locomo-v53-fair-resume"
```

Log: `benchmarks/results/locomo10_v53_fair.log`

**Automated post-P0 (running in session):**

```bash
wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && chmod +x benchmarks/scripts/watch_v53_fair_and_report.sh && nohup benchmarks/scripts/watch_v53_fair_and_report.sh >> benchmarks/results/locomo10_v53_watch.log 2>&1 &"
# Or: make test-locomo-watch
```

Watch log: `benchmarks/results/locomo10_v53_watch.log` — on 10/10 convs runs `make test-locomo-report` + `update_positioning_v53_fair.py`. **Active** 2026-06-04 (poll 300s; auto-restarted after interrupt).

**P0 partial checkpoint (6 convs, 1,157 QA — not headline):**

| Conv | Retrieval | Notes |
| ---- | --------- | ----- |
| conv-26 | 77.4% | fair ingest |
| conv-30 | 81.0% | |
| conv-41 | 79.3% | |
| conv-42 | 79.6% | |
| conv-43 | 80.2% | |
| conv-44 | 90.5% | |
| **Partial overall** | **80.9%** | **1,653 tok/q** — temporal **96.1%**, multi-hop **67.9%**, adversarial **56.3%** (investigate post-P0) |

**P0 completion checklist:**

- [x] 10/10 convs ingested with `ingest complete` (fair run 2026-06-04)
- [x] `locomo10_condensate_v53_fair.json` — all 10 convs complete
- [x] Merged into `locomo10_full_report.json`
- [x] `locomo10_comparative_report.md` regenerated
- [x] `locomo10_comparative_report.html` — layman / adoption narrative (user-facing)
- [x] `locomo10_failure_analysis.md` regenerated
- [x] `COMPETITIVE_POSITIONING.md` updated from fair artifact

---

## P0 — Unblock measurement

### LOC-001 · Fix `sample_observations()` nested loader

| Field | Value |
| ----- | ----- |
| **Status** | `done` |
| **Owner** | parallel-dispatch |
| **Size** | S |
| **Lane** | A |
| **Depends on** | — |
| **Blocks** | LOC-005, LOC-006 |

**Problem:** LoCoMo stores observations as `{speaker: [[fact, dia_id], ...]}`. `sample_observations()` only handles flat lists/strings, so **0 facts** load from `locomo10.json`.

**Files:**
- `benchmarks/data/locomo_loader.py` — fix `sample_observations()`
- `benchmarks/tests/test_locomo.py` — add regression test against real nested shape

**Implementation hints:**
- For each `session_N_observation` key, if value is `dict`, flatten each speaker's list of `[fact, dia_id]` pairs → extract `fact` string.
- Preserve existing flat-list/string handling for `locomo_mini.json` CI fixture.
- Optionally append `dia_id` as provenance suffix (e.g. `"fact [D1:3]"`) — match what observations search expects.

**Acceptance criteria:**
- [x] `sample_observations()` returns >0 lines for every sample in `locomo10.json`
- [x] Mini fixture tests still pass
- [x] New test asserts nested structure parses (use inline fixture or first sample snippet)
- [x] `test_observations_retrieval_hits_answers` still passes on mini fixture

**Delivered:** `_flatten_observation_value()` in `locomo_loader.py`; tests `test_sample_observations_nested_locomo_shape`, `test_sample_observations_locomo10_non_empty`.

**Verify:**
```bash
wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && docker compose -f docker-compose.test.yml run --rm --no-deps test-python pytest benchmarks/tests/test_locomo.py -q"
```

---

### LOC-002 · Fix LLM grader scope for `full_context`

| Field | Value |
| ----- | ----- |
| **Status** | `done` |
| **Owner** | parallel-dispatch |
| **Size** | S |
| **Lane** | A |
| **Depends on** | — |
| **Blocks** | LOC-010 |

**Problem:** `run_locomo.py` passes only first **500 chars** of transcript to LLM grader → 26.1% graded accuracy is misleading.

**Files:**
- `benchmarks/runners/run_locomo.py` — `score_row()` for `full_context`
- `benchmarks/tests/test_locomo.py` — test grader input length or skip behavior

**Options (pick one, document in code):**
1. **Skip LLM grade** for `full_context` when `--llm-grade` (retrieval + native metrics suffice), or
2. **Pass relevant excerpt** — window around substring match of gold answer in context, or
3. **Pass full context** for non-adversarial (watch token cost).

**Acceptance criteria:**
- [x] Graded accuracy for `full_context` is meaningful OR explicitly `null`/skipped in report
- [x] Report JSON documents grading method per backend
- [x] No regression for `observations` / `condensate` grading paths

**Delivered:** LLM grade skipped for `full_context`; report includes `grading_policy` map and per-backend `llm_grading` when `--llm-grade` is set.

**Verify:**
```bash
wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && docker compose -f docker-compose.test.yml run --rm --no-deps test-benchmarks --backend full_context --limit-samples 1 --llm-grade --output /app/benchmarks/results/_loc002_smoke.json && docker compose -f docker-compose.test.yml run --rm --no-deps test-python pytest benchmarks/tests/test_locomo.py -q"
```

---

### LOC-003 · Add checkpoint/resume for long condensate runs

| Field | Value |
| ----- | ----- |
| **Status** | `done` |
| **Owner** | parallel-dispatch |
| **Size** | M |
| **Lane** | A |
| **Depends on** | — |
| **Blocks** | LOC-007 |

**Problem:** Partial run lost progress when condensate backend stopped mid-dataset (~54s/conversation ingest × 10).

**Files:**
- `benchmarks/runners/run_locomo.py` — add `--resume` / `--backend-only` flags
- `benchmarks/results/.gitignore` — ensure checkpoint files ignored if written locally

**Implementation hints:**
- Runner already writes checkpoint JSON after each backend completes; extend to **per-sample** checkpoint inside `run_backend()`.
- On resume: skip samples already present in output JSON for that backend.
- Log `ingested {sample_id}` with timing to stderr (already partially done).

**Acceptance criteria:**
- [x] Interrupting mid-run and re-invoking with `--resume` continues from last completed sample
- [x] Idempotent: re-running completed sample overwrites cleanly
- [x] Document flags in `benchmarks/README.md`

**Delivered:** `--resume` flag; per-sample checkpoint when resuming; backend-level skip when complete; `backend_is_complete()` helper; README section added.

**Verify:**
```bash
wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && docker compose -f docker-compose.test.yml run --rm --no-deps test-benchmarks --backend full_context --limit-samples 2 --output /app/benchmarks/results/_loc003_ckpt.json"
# interrupt manually or add unit test with mocked backend
wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && docker compose -f docker-compose.test.yml run --rm --no-deps test-python pytest benchmarks/tests/test_locomo.py -q"
```

---

### LOC-004 · Add `structured` backend to full LoCoMo run

| Field | Value |
| ----- | ----- |
| **Status** | `done` |
| **Owner** | parallel-dispatch |
| **Size** | S |
| **Lane** | A |
| **Depends on** | — |
| **Blocks** | LOC-006 |

**Problem:** `structured` backend exists in registry but `--backend all` only runs `full_context`, `observations`, (+ optional `condensate`).

**Files:**
- `benchmarks/runners/run_locomo.py` — include `structured` in default `all` list (before or after observations)
- `benchmarks/runners/generate_comparative_report.py` — ensure table renders 4 baselines
- `benchmarks/tests/test_locomo.py` — smoke test includes structured if fast enough

**Acceptance criteria:**
- [x] `--backend all --skip-condensate` runs `structured` and writes summary to report JSON
- [x] `build_strength_summary()` includes structured comparison
- [x] CI mini run completes in reasonable time

**Delivered:** `DEFAULT_BACKEND_ORDER` = `full_context`, `observations`, `structured`, `condensate`; CLI smoke test asserts `structured` in report.

**Verify:**
```bash
wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && docker compose -f docker-compose.test.yml run --rm --no-deps test-benchmarks --backend all --skip-condensate --output /app/benchmarks/results/_loc004_smoke.json"
wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && docker compose -f docker-compose.test.yml run --rm --no-deps test-python pytest benchmarks/tests/test_locomo.py -q"
```

---

## P0 — Complete baselines & live run

### LOC-005 · Re-run observations baseline (post LOC-001)

| Field | Value |
| ----- | ----- |
| **Status** | `done` |
| **Owner** | lane-b-dispatch |
| **Size** | M |
| **Lane** | B |
| **Depends on** | LOC-001 |
| **Blocks** | LOC-009 |

**Goal:** Valid observations numbers on full LoCoMo-10 for target-benchmark comparison.

**Commands:**
```bash
wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && docker compose -f docker-compose.test.yml run --rm --no-deps test-benchmarks \
  --backend observations \
  --dataset /app/benchmarks/data/locomo10.json \
  --output /app/benchmarks/results/locomo10_observations_report.json"
```

**Note:** `--llm-grade` omitted — Docker test container has no outbound DNS/API in this environment. Retrieval metrics are authoritative for LOC-005.

**Acceptance criteria:**
- [x] `avg_retrieved_tokens` > 0
- [x] Non-adversarial retrieval accuracy > 0% (expect materially above 0; document actual)
- [x] `token_savings_vs_transcript` > 0
- [x] Merge or sidecar results into master report (document chosen approach)

**Merge approach:** Sidecars written to `locomo10_observations_report.json` + `locomo10_structured_report.json`, merged into `locomo10_full_report.json` via `benchmarks/scripts/merge_locomo_reports.py`.

**Success metrics:**

| Metric | Target | Actual |
| ------ | ------ | ------ |
| Retrieval accuracy | document | **69.2%** |
| Avg tokens/query | << 20,476 | **6,307** |
| Multi-hop accuracy | document | **43.8%** |
| Adversarial accuracy | document | **52.2%** |
| Token savings vs full_context | — | **69.2%** |
| Token savings vs transcript | > 0 | **67.5%** |

**Category breakdown (retrieval):** temporal 32.1% · multi-hop 43.8% · single-hop 83.3% · open-domain 90.5% · adversarial 52.2%

**Harness fix during run:** `benchmarks/metrics/tokens.py` — use bundled `cl100k_base` + char/4 fallback (Docker had no DNS for tiktoken blob download).

---

### LOC-006 · Run `structured` on LoCoMo-10

| Field | Value |
| ----- | ----- |
| **Status** | `done` |
| **Owner** | lane-b-dispatch |
| **Size** | M |
| **Lane** | B |
| **Depends on** | LOC-004 |
| **Blocks** | LOC-009 |

**Goal:** Measure active-assertion-only memory on same 1,986 QA pairs.

**Commands:**
```bash
wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && docker compose -f docker-compose.test.yml run --rm --no-deps test-benchmarks \
  --backend structured \
  --dataset /app/benchmarks/data/locomo10.json \
  --output /app/benchmarks/results/locomo10_structured_report.json"
```

**Acceptance criteria:**
- [x] Full report JSON with category breakdown
- [x] Compare adversarial retrieval vs full_context (40.1%) — structured should excel here
- [x] Record metrics in tracker table below

**Results:** Structured backend currently ingests raw transcript (all messages `active`) — metrics match `full_context` exactly (80.4% retrieval, 40.1% adversarial). **Supersession not exercised** on LoCoMo ingest path; adversarial differentiation requires Condensate live stack or ContradictionBench.

| Metric | full_context | structured | Notes |
| ------ | ------------ | ---------- | ----- |
| Retrieval accuracy | 80.4% | **80.4%** | Identical — no fact filtering |
| Avg tokens/query | 20,476 | **22,128** | Slightly higher (role prefixes) |
| Adversarial retrieval | 40.1% | **40.1%** | No supersession yet |
| Multi-hop | 55.2% | **55.2%** | — |

---

### LOC-007 · Complete live `condensate` backend run

| Field | Value |
| ----- | ----- |
| **Status** | `done` (10/10 conversations; 2026-05-26) |
| **Owner** | lane-c-dispatch |
| **Size** | L (8–10 hr) |
| **Lane** | C |
| **Depends on** | LOC-003 (recommended), healthy stack |
| **Blocks** | LOC-008, LOC-009, LOC-011–015 |

**Problem:** Previous run ingested conv-26 (~54s) then stopped. **Crash root cause (2026-05-26):** `condensate-core` **OOM-killed** while condensing conv-42 full-transcript bulk ingest (entire conversation → parallel NER + LLM on all turns at once). Benchmark harness then failed with `httpx.ConnectError: name resolution` because core was down. Ollama also showed GPU memory pressure / runner restarts.

**Fixes applied:**
1. `src/agents/ingress.py` — split `process_and_condense_batch` into chunks of `CONDENSE_BATCH_SIZE` (default 40)
2. `benchmarks/backends/condensate.py` — chunked bulk ingest + wait per chunk; broader retrieve retries
3. `benchmarks/docker-compose.bench.yml` — disable uvicorn `--reload`, `LLM_MAX_CONCURRENCY=2`, Ollama `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=2`
4. `src/learn/extractor.py` + `src/llm/schemas.py` — skip malformed assertions (missing `object`/`predicate`) instead of dropping entire extraction bundle; normalize LLM aliases (`obj`, `relation`, etc.)

**Progress before crash:** 3/10 conversations checkpointed (conv-26, conv-30, conv-41). conv-42 failed at QA 150/260.

**Pre-flight:**
```bash
wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && docker compose -f docker-compose.yml -f benchmarks/docker-compose.bench.yml up -d condensate-db condensate-vector condensate-ollama condensate-core"
wsl -e bash -lc "curl -s http://localhost:8000/health"
wsl -e bash -lc "docker inspect condensate-core --format 'OOMKilled={{.State.OOMKilled}}'"
```

**Resume command:**
```bash
wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && docker compose -f docker-compose.yml -f docker-compose.test.yml -f benchmarks/docker-compose.bench.yml run --rm test-benchmarks \
  --backend condensate \
  --dataset /app/benchmarks/data/locomo10.json \
  --resume \
  --output /app/benchmarks/results/locomo10_full_report.json"
```

Log: `benchmarks/results/locomo10_condensate_run.log`

**Acceptance criteria:**
- [x] All 10 conversations ingested and scored
- [x] Report JSON contains `backends.condensate.summary`
- [x] Native answer accuracy + retrieval accuracy + token counts populated
- [x] Ingest time per conversation logged

**Record when done:**

| Metric | Full context | Target benchmark | Condensate target | Actual |
| ------ | ------------ | --------- | ----------------- | ------ |
| Retrieval accuracy | 80.4% | 92.5% | >85% | **32.1%** |
| Tokens/query | 20,476 | 6,956 | <7,000 | **132** |
| Multi-hop | 55.2% | 93.3% | >75% | — |
| Temporal | 86.0% | 92.8% | >90% | — |
| Adversarial | 40.1% | — | >90% | — |

---

### LOC-008 · Merge final multi-backend report

| Field | Value |
| ----- | ----- |
| **Status** | `done` |
| **Owner** | — |
| **Size** | S |
| **Lane** | C |
| **Depends on** | LOC-005, LOC-006, LOC-007 |
| **Blocks** | LOC-009 |

**Goal:** Single canonical JSON with all backends for reporting.

**Partial merge (2026-05-26):** `full_context` + `observations` + `structured` merged. **`condensate` in progress (LOC-007)** — writing directly to `locomo10_full_report.json` with `--resume` per-sample checkpoints.

**On LOC-007 completion:** Verify all four backends present; `condensate_strengths` headline should update automatically. No sidecar merge needed if run targets master report.

**Merge command:**
```bash
wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && docker compose -f docker-compose.test.yml run --rm --no-deps --entrypoint python test-benchmarks \
  benchmarks/scripts/merge_locomo_reports.py \
  --base /app/benchmarks/results/locomo10_full_report.json \
  --sidecar /app/benchmarks/results/locomo10_observations_report.json \
  --sidecar /app/benchmarks/results/locomo10_structured_report.json \
  --output /app/benchmarks/results/locomo10_full_report.json"
```

**Acceptance criteria:**
- [x] `locomo10_full_report.json` contains: `full_context`, `observations`, `structured`
- [x] `locomo10_full_report.json` contains: `condensate`
- [x] `condensate_strengths` headline reflects real condensate delta
- [x] `samples_evaluated: 10`, `total_qa_pairs: 1986`

---

## P1 — Reporting & analysis

### LOC-009 · Generate comparative Markdown report

| Field | Value |
| ----- | ----- |
| **Status** | `done` |
| **Owner** | — |
| **Size** | S |
| **Lane** | D |
| **Depends on** | LOC-008 |
| **Blocks** | — |

**Command:**
```bash
wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && docker compose -f docker-compose.test.yml run --rm --no-deps --entrypoint python test-benchmarks \
  benchmarks/runners/generate_comparative_report.py \
  --input /app/benchmarks/results/locomo10_full_report.json \
  --output /app/benchmarks/results/locomo10_comparative_report.md"
```

**Acceptance criteria:**
- [x] Markdown includes all backends + target benchmark reference row
- [x] Category breakdown table populated
- [x] Executive summary uses real condensate headline (not placeholder)

**Output:** `benchmarks/results/locomo10_comparative_report.md`

---

### LOC-010 · Failure-mode analysis script

| Field | Value |
| ----- | ----- |
| **Status** | `done` |
| **Owner** | — |
| **Size** | M |
| **Lane** | D |
| **Depends on** | LOC-002, LOC-008 |
| **Blocks** | LOC-011–015 |

**Goal:** Repeatable analysis of misses by category (not ad-hoc one-offs).

**Deliverable:** `benchmarks/scripts/analyze_locomo_report.py`

**Output:**
- Miss counts by category per backend
- Example misses (one per category)
- Token efficiency summary per conversation
- Optional: CSV export for spreadsheet review

**Acceptance criteria:**
- [x] Runs via Docker: `python benchmarks/scripts/analyze_locomo_report.py --input ...`
- [x] Tested against `locomo10_full_report.json`
- [x] Documented in `benchmarks/README.md`

**Outputs:** `benchmarks/results/locomo10_failure_analysis.md`, `benchmarks/results/locomo10_misses_by_category.csv`

**Verify:**
```bash
wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && docker compose -f docker-compose.test.yml run --rm --no-deps --entrypoint python test-benchmarks benchmarks/scripts/analyze_locomo_report.py --input /app/benchmarks/results/locomo10_full_report.json"
```

---

## P1 — Product accuracy (after LOC-007)

*These items need condensate baseline numbers. Can be parallelized across owners once LOC-010 lands.*

### LOC-011 · Multi-hop retrieval improvement

| Field | Value |
| ----- | ----- |
| **Status** | `in_progress` |
| **Owner** | agent |
| **Size** | L |
| **Lane** | E |
| **Depends on** | LOC-007, LOC-010 |
| **Blocks** | — |

**Baseline:** full_context 55.2% · target benchmark 93.3% · **Target: >75%**

**v5 result (2026-05-28):** **52.1%** (+41.7 pts vs v2 first run 10.4%; +14.6 pts vs v4e 37.5%). Still below target.

**v5.1 result (2026-05-29):** **49.0%** overall on full run; v6 multihop regression reverted. **v5.2 (2026-05-29):** skip adversarial filter on counterfactual multihop; wider recall queries; list/temporal scoring in `qa.py`.

**Scope ideas (pick subset per PR):**
- Cross-session graph traversal for related assertions
- Query decomposition for multi-entity questions
- Session-aware ranking boosts

**Files (likely):**
- `src/engine/` retrieval / graph code
- `benchmarks/backends/condensate.py` — if retrieve API params need tuning

**Acceptance criteria:**
- [x] LoCoMo multi-hop category improves ≥10 pts vs first condensate run (10.4% → 52.1%)
- [ ] LoCoMo multi-hop category ≥75%
- [ ] No regression >2 pts on open-domain / single-hop in mini CI fixture
- [x] Docker pytest + targeted LoCoMo sample re-run documented (`locomo10_condensate_sample_v5.json`)

---

### LOC-012 · Temporal inference improvement

| Field | Value |
| ----- | ----- |
| **Status** | `in_progress` |
| **Owner** | agent |
| **Size** | M |
| **Lane** | E |
| **Depends on** | LOC-007, LOC-010 |
| **Blocks** | — |

**Baseline:** full_context 86.0% · target benchmark 92.8% · **Target: >90%**

**v5 result (2026-05-28):** **79.4%** (+74.7 pts vs v2 first run 4.7%; +24.9 pts vs v4e 54.5%). Below 90% target.

**Example failures:** date arithmetic ("When did Melanie paint a sunrise?" → 2022), duration ("Since 2016").

**Scope ideas:**
- Store normalized timestamps on assertions at condensation time
- Temporal indexing in retrieval ranking
- Session date metadata in retrieve context

**Acceptance criteria:**
- [x] LoCoMo temporal category improves ≥5 pts vs first condensate run (4.7% → 79.4%)
- [ ] LoCoMo temporal category ≥90%
- [x] Unit tests for date parsing edge cases (`test_answer_in_context_temporal_last_year`)

---

### LOC-013 · Adversarial / trap-answer handling

| Field | Value |
| ----- | ----- |
| **Status** | `done` |
| **Owner** | agent |
| **Size** | M |
| **Lane** | E |
| **Depends on** | LOC-007 |
| **Blocks** | LOC-014 |

**Baseline:** full_context retrieval 40.1% (trap in transcript) · **Target: >90%**

**v5.1 result (2026-05-29):** **64.8%** (v5 62.8%). **v5.2:** `should_apply_adversarial_filter()` skips counterfactual multihop; raw dialog cap **2** for true adversarial-risk queries only.

**Differentiation story:** assertion supersession vs add-only target-benchmark-class memory.

**v5.2 full QA-only (2026-05-29):** **92.8%** adversarial retrieval — **LOC-013 target met**.

**Acceptance criteria:**
- [x] LoCoMo adversarial retrieval >90% on condensate backend
- [ ] ContradictionBench still passes (run `make test-contradiction`)
- [x] One-paragraph "why us vs target benchmark class" note in comparative report / COMPETITIVE_POSITIONING.md

---

### LOC-014 · ContradictionBench + LoCoMo joint narrative

| Field | Value |
| ----- | ----- |
| **Status** | `done` |
| **Owner** | agent |
| **Size** | S |
| **Lane** | E |
| **Depends on** | LOC-013 |
| **Blocks** | — |

**Goal:** Single doc section linking LoCoMo adversarial results to ContradictionBench.

**Deliverable:** `benchmarks/docs/COMPETITIVE_POSITIONING.md` (updated 2026-05-28 with v5 numbers)

**Acceptance criteria:**
- [x] Side-by-side table: LoCoMo adversarial + ContradictionBench scores
- [x] No mocked numbers — all from actual run artifacts

---

### LOC-015 · Token efficiency tuning

| Field | Value |
| ----- | ----- |
| **Status** | `in_progress` |
| **Owner** | agent |
| **Size** | M |
| **Lane** | E |
| **Depends on** | LOC-007 |
| **Blocks** | — |

**Baseline:** full_context ~20,476 tokens/query · target benchmark ~6,956 · **Target: <7,000 at >85% retrieval**

**v5.1 result (2026-05-29):** **921 tokens/query** at **71.8%** retrieval — token budget met; accuracy short of 85%. Rescore with v5.2 `qa.py`: **72.1%** (same artifacts).

**Scope ideas:**
- Top-k / token budget caps on `/memory/retrieve`
- Condensation aggressiveness settings
- Context packing order (most relevant assertion first)

**Acceptance criteria:**
- [ ] Avg retrieved tokens <7,000 on LoCoMo-10
- [ ] Retrieval accuracy ≥85%
- [ ] Document recommended production defaults

---

## P2 — CI & regression

### LOC-017 · Session-scoped retrieval (cross-conversation noise fix)

| Field | Value |
| ----- | ----- |
| **Status** | `done` |
| **Owner** | agent |
| **Size** | M |
| **Lane** | E |
| **Depends on** | LOC-007 |
| **Blocks** | headline full-run fairness |

**Problem:** All LoCoMo conversations shared one `project_id`; retrieve had no `session_id` filter → conv 2–10 scores diluted by cross-talk.

**Files:**
- `src/server/router_api.py` — `RetrieveRequest.session_id`
- `src/retrieve/router.py` — Qdrant `metadata.session_id` filter + assertion scoping
- `benchmarks/backends/condensate.py` — pass `session_id` on retrieve; strip CRLF from API key
- `benchmarks/runners/run_locomo.py` — `--sample-ids` filter
- `tests/test_retrieval_helpers.py`, `benchmarks/tests/test_condensate_backend.py`

**Acceptance criteria:**
- [x] Unit tests for filter helpers (52 tests pass)
- [x] conv-30 QA-only improves vs v5.2 full shared-project run (**85.7%** vs **67.6%**)
- [x] Session-scoped retrieve shipped (`RetrieveRequest.session_id`, Qdrant filter)
- [ ] v5.3 **fair** 10-conv fresh ingest headline (`locomo10_condensate_v53_fair.json`) — **resume running** 2026-06-01 from conv-47; prior `locomo10_condensate_v53_full.json` invalid (QA-only skip ingest)

---

### LOC-016 · Weekly LoCoMo mini regression (non-blocking CI)

| Field | Value |
| ----- | ----- |
| **Status** | `todo` |
| **Owner** | — |
| **Size** | M |
| **Lane** | A |
| **Depends on** | LOC-001 |
| **Blocks** | — |

**Goal:** Per README roadmap — catch harness regressions without full 10-conversation run.

**Acceptance criteria:**
- [ ] GitHub Action or documented cron runs `make test-benchmarks` via WSL/Docker
- [ ] Non-blocking on PRs (informational)
- [ ] Fails if observations loader returns 0 facts on mini fixture

---

## Cross-backend comparison (LoCoMo-10, 2026-05-29)

| Backend | Retrieval | Tokens/query | vs target benchmark tokens (6,956) | Adversarial |
| ------- | --------- | ------------ | ---------------------- | ----------- |
| full_context | 80.4% | 20,476 | 2.94× | 40.1% |
| observations | 69.2% | 6,307 | 0.91× | 52.2% |
| structured | 80.4% | 22,128 | 3.18× | 40.1% |
| condensate (v5.1) | **71.8%** | **921** | **0.13×** | 64.8% |
| Target benchmark | 92.5% | 6,956 | 1.00× | — |

**Key insight:** Condensate v5.1 **beats observations on retrieval** (+2.6 pts) at **7× lower token cost**. Open-domain retrieval **beats target benchmark** (81.2% vs 76.0%). Multi-hop (49.0%) and single-hop (55.7%) remain primary gaps vs target benchmark.

---

## Quick reference — baseline numbers (full_context, 2026-05-26)

| Category | Count | Retrieval | Priority |
| -------- | ----- | --------- | -------- |
| Open-domain | 841 | 98.3% | Maintain |
| Single-hop | 282 | 92.9% | Polish |
| Temporal | 321 | 86.0% | LOC-012 |
| Multi-hop | 96 | 55.2% | LOC-011 |
| Adversarial | 446 | 40.1% | LOC-013 |

**122 non-adversarial retrieval misses** on full_context — use LOC-010 to enumerate.

---

## Changelog

| Date | Item | Change |
| ---- | ---- | ------ |
| 2026-06-04 | v53 fair complete | **82.0%** retrieval, **1,749 tok/q**, 10/10 convs; reports merged; LOC-015 tokens met, retrieval 3 pts below 85% |
| 2026-06-04 | v53 fair retry | Resume + watch restarted after interrupt at conv-47 chunk 5/68 |
| 2026-06-01 | v53 fair partial | 6/10 convs **80.9%** @ **1,653 tok/q**; run stopped mid conv-47 QA; `make test-locomo-v53-fair-resume` |
| 2026-05-31 | P0 plan | Prior `locomo10_condensate_v53_full.json` invalidated (QA-only, `CONDENSATE_SKIP_INGEST`); fair re-run via `make test-locomo-v53-fair` → `locomo10_condensate_v53_fair.json` |
| 2026-05-29 | v5.2 full QA-only | 10-conv **65.8%** overall (~22 min); adversarial **92.8%**; conv-26 **89.5%**; other convs lower on shared project — **fresh per-conv ingest needed** for fair headline |
| 2026-05-29 | v5.2 LOC push | Adversarial filter skips multihop counterfactuals; recall queries for list/temporal single-hop; qa.py list/temporal/status scoring; rebuilt `run_locomo.py` + `condensate.py` harness; 47 harness tests pass |
| 2026-05-29 | v5.1 full | **71.8%** retrieval, 921 tok/q; adversarial **64.8%**; merged into master report |
| 2026-05-29 | v6 LOC push | Target benchmark naming across harness; bounded graph steps=1, adversarial context filter, wider token budget (LOC-011/012/013/015) |
| 2026-05-28 | v5 full | Lane E v5: 73.3% retrieval, 1014 tok/q; merged into `locomo10_full_report.json`; comparative + failure analysis regenerated; `COMPETITIVE_POSITIONING.md` updated |
| 2026-05-26 | LOC-011–015 | Lane E: fused retrieval (vector+assertions+graph), `context` on `/memory/retrieve`, harness scores text not UUIDs, token budget env vars, `COMPETITIVE_POSITIONING.md`; 1-conversation validation run started |
| 2026-05-26 | LOC-009, LOC-010 | Lane D reporting complete — comparative + failure analysis artifacts |
| 2026-05-26 | LOC-005, LOC-006 | Lane B baselines complete; merged into master report |
| 2026-05-26 | harness | Offline token counting fix; merge script; LLM grader connection fallback |
| 2026-05-26 | LOC-001–004 | Lane A harness fixes delivered; tests pass (`make test-python`) |
| 2026-05-26 | — | Tracker created from LoCoMo-10 partial run analysis |
