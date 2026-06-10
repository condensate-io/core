"""Tests for ContradictionBench runner."""

from benchmarks.runners.run_contradiction import run_contradiction


def test_run_contradiction_smoke():
    report = run_contradiction()
    assert report["summary"]["total"] >= 1
    assert report["summary"]["forbidden_leaks"] == 0
    assert report["summary"]["retrieval_accuracy"] == 1.0
