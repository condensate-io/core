"""Tests for Astrocyte Evidence Verifier."""

from src.retrieve.evidence_verifier import verify_evidence, abstention_answer
from src.retrieve.recall_gate import build_query_plan


def test_verify_direct_support():
    plan = build_query_plan("What tea does Alice prefer?")
    result = verify_evidence(
        "What tea does Alice prefer?",
        ["Alice prefers jasmine tea in session 7"],
        plan=plan,
        confidence_score=0.9,
    )
    assert result.answerable is True
    assert result.support_level == "direct"
    assert result.abstain_recommended is False


def test_verify_abstention_when_empty():
    plan = build_query_plan("What country would Alice visit if she had never changed jobs?")
    result = verify_evidence(
        "What country would Alice visit if she had never changed jobs?",
        [],
        plan=plan,
        confidence_score=0.0,
    )
    assert result.answerable is False
    assert result.abstain_recommended is True
    assert "memory" in abstention_answer(result).lower()


def test_verify_indirect_support():
    plan = build_query_plan("What hobbies does Bob enjoy?")
    result = verify_evidence(
        "What hobbies does Bob enjoy?",
        ["Bob mentioned camping once"],
        plan=plan,
        confidence_score=0.55,
    )
    assert result.support_level in ("indirect", "direct", "none")
