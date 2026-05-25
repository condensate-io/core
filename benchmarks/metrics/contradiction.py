"""Score retrieved context for undetected contradictory facts."""

from __future__ import annotations


def detect_conflicts(retrieved_context: str, forbidden_phrases: list[str]) -> list[str]:
    """Return forbidden phrases still present in retrieved context (case-insensitive)."""
    if not retrieved_context:
        return list(forbidden_phrases)
    lowered = retrieved_context.lower()
    return [phrase for phrase in forbidden_phrases if phrase.lower() in lowered]


def score_case(retrieved_context: str, case: dict) -> dict:
    """Score one ContradictionBench case."""
    forbidden = case.get("forbidden_in_context", [])
    undetected = detect_conflicts(retrieved_context, forbidden)
    return {
        "case_id": case["id"],
        "passed": len(undetected) == 0,
        "undetected_conflicts": undetected,
        "query": case.get("query", ""),
    }


def summarize_results(results: list[dict]) -> dict:
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    return {
        "passed": passed,
        "total": total,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "undetected_conflict_rate": round((total - passed) / total, 4) if total else 0.0,
    }
