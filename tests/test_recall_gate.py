"""Tests for Astrocyte Recall Gate."""

from src.retrieve.recall_gate import (
    AstrocyteRecallGate,
    build_query_plan,
    classify_question_type,
    is_adversarial_phrasing,
)


def test_classify_temporal_update():
    q = "When did Alice eventually decide to switch jobs?"
    assert classify_question_type(q) == "temporal_update"


def test_classify_abstention():
    q = "What would Bob pursue if he hadn't changed careers?"
    assert classify_question_type(q) == "abstention"


def test_classify_exact_fact_default():
    q = "What color is the kitchen table?"
    assert classify_question_type(q) == "exact_fact"


def test_build_query_plan_sets_modes_and_threshold():
    plan = build_query_plan("When did Carol eventually change her job start date?")
    assert plan.question_type == "temporal_update"
    assert plan.requires_latest_state is True
    assert "temporal_chain" in plan.retrieval_modes
    assert plan.confidence_threshold >= 0.7


def test_astrocyte_gate_classify():
    gate = AstrocyteRecallGate()
    plan = gate.classify("Describe Alice's personality traits", keywords=["alice"])
    assert plan.question_type == "relationship"
    assert plan.requires_persona is True
    assert plan.strategy == "research"


def test_complexity_aware_budget_simple_vs_multihop():
    # Baseline questions keep tier-2 depth (never reduced below known-good).
    simple = build_query_plan("What color is the kitchen table?")
    assert simple.complexity == 2
    assert simple.recall_budget == 16

    multihop = build_query_plan(
        "What fields would Caroline be likely to pursue?", is_multihop=True
    )
    assert multihop.complexity == 3
    assert multihop.recall_budget >= 20
    assert multihop.recall_budget > simple.recall_budget


def test_adversarial_phrasing_detection():
    assert is_adversarial_phrasing(
        "What are Melanie's plans for the summer with respect to adoption?"
    )
    assert is_adversarial_phrasing("What would Bob pursue if he hadn't changed careers?")
    assert not is_adversarial_phrasing("What is Alice's favorite tea?")


def test_adversarial_plan_tightens_recall_and_sets_trap_filter():
    plan = build_query_plan(
        "What are Melanie's plans for the summer with respect to adoption?"
    )
    assert plan.requires_trap_filter is True
    assert plan.requires_abstention_check is True
    assert plan.recall_budget <= 8


def test_entity_swap_plan_sets_swap_flag_not_trap_filter():
    plan = build_query_plan("What does Melanie's necklace symbolize?")
    assert plan.requires_entity_swap is True
    assert plan.requires_trap_filter is False
    assert plan.requires_abstention_check is True
