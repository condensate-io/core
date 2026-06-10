"""LOC-024: source-turn hydration from observation dia_id provenance."""

from unittest.mock import MagicMock
import uuid

import pytest

from src.db.models import EpisodicItem
from src.retrieve.router import (
    MemoryRouter,
    extract_observation_dia_ids,
    format_source_turn_line,
    is_structured_context_line,
    source_turn_hydration_enabled,
)


def test_extract_observation_dia_ids_dedupes_and_preserves_order():
    items = [
        "[observation D6:6] Melanie's kids love dinosaurs.",
        "[score=1.0, session @ 1:56 pm] Caroline: hello",
        "[observation D4:8] another fact",
        "[observation D6:6] duplicate id",
    ]
    assert extract_observation_dia_ids(items) == ["D6:6", "D4:8"]


def test_source_turn_line_and_structured_marker():
    line = format_source_turn_line(
        "Melanie: The kids love dinosaurs and nature.",
        {"dia_id": "D6:6", "session_date": "1:56 pm on 8 May, 2023"},
    )
    assert "[source turn D6:6]" in line
    assert "dinosaurs" in line
    assert is_structured_context_line(line)


def test_source_turn_hydration_enabled_benchmark_default():
    assert source_turn_hydration_enabled(benchmark_mode=True) is True
    assert source_turn_hydration_enabled(benchmark_mode=False) is False


def test_hydrate_source_turns_appends_dialog_rows():
    db = MagicMock()
    qdrant = MagicMock()
    router = MemoryRouter(db, qdrant)

    project_id = uuid.uuid4()
    row = EpisodicItem(
        id=uuid.uuid4(),
        project_id=project_id,
        source="benchmark",
        text="Melanie: The kids love dinosaurs and nature.",
        metadata_={"dia_id": "D6:6", "role": "Melanie"},
    )
    db.execute.return_value.scalars.return_value.all.return_value = [row]

    context = ["[observation D6:6] Melanie enjoys time with her kids."]
    sources = ["obs-1"]
    merged, merged_sources = router._hydrate_source_turns(project_id, context, sources)

    assert len(merged) == 2
    assert any("[source turn D6:6]" in line for line in merged)
    assert len(merged_sources) == 2
    assert str(row.id) in merged_sources


def test_hydrate_source_turns_skips_when_no_observation_ids():
    db = MagicMock()
    router = MemoryRouter(db, MagicMock())
    context = ["Assertion: Bob likes cats (conf: 0.9)"]
    sources = ["a1"]
    merged, merged_sources = router._hydrate_source_turns(uuid.uuid4(), context, sources)
    assert merged == context
    assert merged_sources == sources
    db.execute.assert_not_called()
