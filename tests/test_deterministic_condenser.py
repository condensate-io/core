"""LOC-025: L3 condensation preserves list and activity lines."""

from src.engine.deterministic import DeterministicCondenser


def test_l3_condensation_keeps_list_and_activity_lines():
    text = (
        "Melanie: Thanks for checking in.\n"
        "Melanie: The kids love dinosaurs, nature, and painting.\n"
        "Melanie: I prioritize running, reading, and violin for self-care."
    )
    result = DeterministicCondenser().process(text)
    condensed = result["condensed"].lower()
    assert "dinosaurs" in condensed
    assert "running" in condensed or "violin" in condensed
