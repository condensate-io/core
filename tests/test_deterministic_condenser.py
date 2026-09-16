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


def test_l3_code_mode_extracts_imports_and_defs():
    code = (
        "import os\n"
        "from src.engine.thread_shard import get_thread_shard\n\n"
        "MAX_RETRIES = 3\n\n"
        "class Widget:\n"
        "    def process(self):\n"
        "        pass\n"
    )
    result = DeterministicCondenser().process(code, code_mode=True)

    assert result["layer"] == "Condensed Memory (Heuristic L3 - Code)"
    entity_names = {e.name for e in result["entities"]}
    assert "os" in entity_names
    assert "src.engine.thread_shard" in entity_names
    assert "Widget" in entity_names
    assert "process" in entity_names
    assert "MAX_RETRIES" in entity_names
    # No facts (subject/predicate/object triplets) synthesized for code.
    assert result["facts"] == []


def test_l3_code_mode_handles_no_symbols_gracefully():
    result = DeterministicCondenser().process("x = 1\ny = 2\n", code_mode=True)
    assert result["layer"] == "Condensed Memory (Heuristic L3 - Code)"
    assert isinstance(result["entities"], list)

