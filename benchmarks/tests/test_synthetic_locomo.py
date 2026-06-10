"""Tests for synthetic LoCoMo generator."""

from benchmarks.data.generate_synthetic_locomo import generate_conversation, load_synthetic_samples


def test_generate_conversation_shape():
    sample = generate_conversation(num_sessions=12, turns_per_session=6, seed=7)
    assert sample["conversation"]["sessions"]
    assert sample["qa"]
    assert any(q["memory_type"] == "temporal_change" for q in sample["qa"])
    assert any(q["should_abstain"] for q in sample["qa"])


def test_load_synthetic_samples():
    samples = load_synthetic_samples()
    assert samples
    assert "qa" in samples[0]
