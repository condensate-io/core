"""LOC-027: unit tests for the mini regression gate."""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.scripts.check_locomo_mini_regression import check_regression

BASELINE = Path("benchmarks/results/baselines/locomo_mini_condensate_baseline.json")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_regression_passes_on_baseline_match():
    baseline = _load(BASELINE)
    failures = check_regression(baseline, baseline)
    assert failures == []


def test_regression_fails_on_overall_drop():
    baseline = _load(BASELINE)
    regressed = json.loads(json.dumps(baseline))
    summary = regressed["backends"]["condensate"]["summary"]
    summary["retrieval_hits"] = 3
    summary["retrieval_accuracy"] = 0.6
    failures = check_regression(regressed, baseline)
    assert any("overall" in f for f in failures)


def test_regression_fails_on_category_drop():
    baseline = _load(BASELINE)
    regressed = json.loads(json.dumps(baseline))
    cat = regressed["backends"]["condensate"]["summary"]["by_category"]["single-hop"]
    cat["hits"] = 0
    cat["accuracy"] = 0.0
    failures = check_regression(regressed, baseline)
    assert any("single-hop" in f for f in failures)
