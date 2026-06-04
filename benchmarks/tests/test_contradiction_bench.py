"""ContradictionBench unit tests — run via Docker pytest."""

from __future__ import annotations

from benchmarks.backends.full_context import FullContextBackend
from benchmarks.backends.structured import StructuredMemoryBackend
from benchmarks.data.generate_contradiction_cases import build_cases, load_cases
from benchmarks.metrics.contradiction import detect_conflicts, score_case, summarize_results


def test_build_cases_count():
    assert len(build_cases()) == 50


def test_load_cases_from_disk():
    cases = load_cases()
    assert len(cases) == 50
    assert cases[0]["id"] == "cb-001"


def test_detect_conflicts_finds_stale_fact():
    context = "user: Server 1 is down\nuser: Server 1 is up"
    found = detect_conflicts(context, ["Server 1 is down"])
    assert found == ["Server 1 is down"]


def test_structured_backend_passes_contradiction_case():
    case = build_cases(1)[0]
    backend = StructuredMemoryBackend()
    backend.reset(case["id"])
    backend.add(case["id"], case["messages"])
    context = backend.search(case["id"], case["query"])
    result = score_case(context, case)
    assert result["passed"] is True


def test_full_context_backend_fails_contradiction_case():
    case = build_cases(1)[0]
    backend = FullContextBackend()
    backend.reset(case["id"])
    backend.add(case["id"], case["messages"])
    context = backend.search(case["id"], case["query"])
    result = score_case(context, case)
    assert result["passed"] is False
    assert result["undetected_conflicts"]


def test_summarize_results():
    results = [{"passed": True}, {"passed": False}, {"passed": True}]
    summary = summarize_results(results)
    assert summary["passed"] == 2
    assert summary["total"] == 3
    assert summary["pass_rate"] == 0.6667
