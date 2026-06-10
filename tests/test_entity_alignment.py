"""Tests for query-only entity–evidence alignment (production-fair adversarial)."""

from src.retrieve.entity_alignment import (
    entity_evidence_aligned,
    episodic_hit_admissible,
    filter_entity_evidence_context,
    filter_swap_trap_context,
    is_adversarial_risk_query,
    is_entity_swap_trap,
    is_specific_attribute_query,
    supplementary_vector_queries_adversarial,
)


def test_specific_attribute_detects_necklace_question():
    assert is_specific_attribute_query("What does Melanie's necklace symbolize?")
    assert is_specific_attribute_query(
        "What are Melanie's plans for the summer with respect to adoption?"
    )


def test_specific_attribute_detects_expanded_swap_patterns():
    assert is_specific_attribute_query("What type of instrument does Caroline play?")
    assert is_specific_attribute_query(
        "What kind of counseling workshop did Melanie attend recently?"
    )
    assert is_specific_attribute_query(
        "What did Caroline and her family see during their camping trip last year?"
    )
    assert is_specific_attribute_query("Is Oscar Melanie's pet?")
    assert is_specific_attribute_query("What is Jon's favorite style of painting?")


def test_entity_swap_trap_narrower_than_broad_attribute():
    assert is_entity_swap_trap("What does Melanie's necklace symbolize?")
    assert is_specific_attribute_query("What book is Gina currently reading?")
    assert not is_entity_swap_trap("What book is Gina currently reading?")
    assert is_specific_attribute_query("What game is Joanna currently playing?")
    assert not is_entity_swap_trap("What game is Joanna currently playing?")


def test_open_domain_book_context_not_swap_filtered():
    query = "What book is Gina currently reading?"
    items = [
        "[observation D2:4] Gina is currently reading The Lean Startup.",
        "Gina enjoys entrepreneurship books.",
    ]
    filtered, _ = filter_swap_trap_context(query, items, ["a", "b"])
    assert len(filtered) == 2
    assert "lean startup" in filtered[0].lower()


def test_valid_possessive_single_hop_not_adversarial_risk():
    assert not is_adversarial_risk_query("What do Melanie's kids like?")
    assert not is_adversarial_risk_query("When did Caroline go to the LGBTQ support group?")


def test_counterfactual_still_adversarial_risk():
    assert is_adversarial_risk_query(
        "What would Bob pursue if he hadn't changed careers?"
    )


def test_entity_filter_strips_unproven_attribute_lines():
    query = "What does Melanie's necklace symbolize?"
    items = [
        "[observation D4:3] Melanie's necklace symbolizes love, faith, and strength.",
        "Melanie's necklace symbolizes love, faith, and strength.",
        "[observation D5:10] Pottery helps Melanie express emotions.",
    ]
    sources = ["a", "b", "c"]
    filtered, _ = filter_entity_evidence_context(query, items, sources)
    assert any("D4:3" in line for line in filtered)
    assert not any(
        line.startswith("Melanie's necklace") and "[observation" not in line
        for line in filtered
    )


def test_entity_evidence_aligned_keeps_non_asserting_background():
    query = "What does Melanie's necklace symbolize?"
    background = "[observation D5:10] Pottery helps Melanie express emotions."
    assert entity_evidence_aligned(query, background)


def test_episodic_hit_requires_dia_id_and_subject_for_adversarial():
    query = "What does Melanie's necklace symbolize?"
    assert episodic_hit_admissible(
        query,
        "Melanie's necklace symbolizes love.",
        {"dia_id": "D4:3"},
    )
    assert not episodic_hit_admissible(
        query,
        "Melanie's necklace symbolizes love.",
        {},
    )
    assert not episodic_hit_admissible(
        query,
        "Caroline loves pottery.",
        {"dia_id": "D5:10"},
    )
    assert episodic_hit_admissible(
        query,
        "[observation D4:3] Melanie discussed faith.",
        {"kind": "observation"},
    )


def test_episodic_hit_admits_all_for_non_adversarial():
    query = "What do Melanie's kids like?"
    assert episodic_hit_admissible(query, "Kids enjoy soccer.", {})


def test_adversarial_supplementary_query_is_entity_focused():
    query = "What country is Melanie's grandma from?"
    extras = supplementary_vector_queries_adversarial(
        query, ["melanie", "country", "grandma"]
    )
    assert extras
    assert "melanie" in extras[0].lower()


def test_swap_trap_filter_strips_cross_entity_trap_answer():
    query = "What does Melanie's necklace symbolize?"
    items = [
        "[observation D4:3] Caroline received a special necklace symbolizing love, faith, and strength.",
        "[observation D5:10] Pottery helps Melanie express emotions.",
        "Melanie's necklace symbolizes love, faith, and strength.",
    ]
    sources = ["a", "b", "c"]
    filtered, _ = filter_swap_trap_context(query, items, sources)
    joined = "\n".join(filtered).lower()
    assert "love, faith, and strength" not in joined
    assert "symboliz" not in joined
    assert any("pottery" in line.lower() for line in filtered)


def test_swap_trap_filter_keeps_disambiguation_without_trap():
    query = "Is Oscar Melanie's pet?"
    items = [
        "[observation D13:3] Caroline has a guinea pig named Oscar.",
        "[observation D13:4] Melanie has pets including another cat named Bailey.",
    ]
    filtered, _ = filter_swap_trap_context(query, items, ["a", "b"])
    assert len(filtered) == 2
    assert not any(" yes " in f" {line.lower()} " for line in filtered)


def test_swap_trap_supplementary_query_includes_attribute_only():
    query = "What does Melanie's necklace symbolize?"
    extras = supplementary_vector_queries_adversarial(
        query, ["melanie", "necklace", "symbolize"]
    )
    assert len(extras) >= 2
    assert "melanie" in extras[0].lower()
    assert "melanie" not in extras[1].lower()
    assert "necklace" in extras[1].lower()
