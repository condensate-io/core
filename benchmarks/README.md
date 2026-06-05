# Condensates benchmarks

LoCoMo and ContradictionBench harnesses live here. Run via WSL + Docker (`make test-benchmarks`, `make test-locomo-report`).

| Artifact | Path |
| -------- | ---- |
| Canonical v5.3 fair run | `results/locomo10_condensate_v53_fair.json` (local; gitignored) |
| Published HTML report | `results/locomo10_comparative_report.html` |
| Work tracker | `../ROADMAP_IMPLEMENTATION_TRACKER.md` |

**Report pipeline:** `make test-locomo-report` merges the fair sidecar into `locomo10_full_report.json`, regenerates MD/HTML, and refreshes failure analysis.
