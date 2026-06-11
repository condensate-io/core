"""LOC-024: source-turn hydration from observation dia_id provenance."""

from unittest.mock import MagicMock
import uuid

import pytest

from src.db.models import EpisodicItem
from src.retrieve.router import (
    MemoryRouter,
    collect_hydration_dia_ids,
    extract_observation_dia_ids,
    format_source_turn_line,
    is_structured_context_line,
    merge_hydrated_source_turns,
    observation_line_thin_for_query,
    query_suggests_verbatim_detail,
    should_expand_source_hydration,
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
    assert merged[0].startswith("[source turn D6:6]")
    assert "[observation D6:6]" in merged[1]
    assert len(merged_sources) == 2
    assert str(row.id) in merged_sources


def test_merge_hydrated_source_turns_places_turn_before_observation():
    context = ["[observation D6:6] Melanie enjoys time with her kids."]
    sources = ["obs-1"]
    hydrated = [
        "[source turn D6:6] Melanie: The kids love dinosaurs and nature.",
    ]
    hydrated_sources = ["turn-1"]
    merged, merged_src = merge_hydrated_source_turns(
        context, sources, hydrated, hydrated_sources
    )
    assert merged[0].startswith("[source turn D6:6]")
    assert "[observation D6:6]" in merged[1]
    assert merged_src == ["turn-1", "obs-1"]


def test_loc030_verbatim_detail_and_thin_observation():
    query = "What do Melanie's kids like?"
    thin = "[observation D6:6] Melanie enjoys time with her kids."
    assert query_suggests_verbatim_detail(query)
    assert observation_line_thin_for_query(query, thin)
    assert should_expand_source_hydration(query, [thin])


def test_collect_hydration_dia_ids_merges_expansion():
    context = ["[observation D6:6] Melanie enjoys time with her kids."]
    ids = collect_hydration_dia_ids(context, ["D4:8", "D6:6"])
    assert ids == ["D6:6", "D4:8"]


def test_hydrate_expands_entity_turns_for_thin_observation():
    db = MagicMock()
    router = MemoryRouter(db, MagicMock())
    project_id = uuid.uuid4()
    query = "What do Melanie's kids like?"

    turn_d6 = EpisodicItem(
        id=uuid.uuid4(),
        project_id=project_id,
        source="benchmark",
        text="Melanie: The kids love dinosaurs and nature.",
        metadata_={"dia_id": "D6:6"},
    )
    turn_d4 = EpisodicItem(
        id=uuid.uuid4(),
        project_id=project_id,
        source="benchmark",
        text="Melanie: We went to the museum, kids loved the dinosaur exhibit.",
        metadata_={"dia_id": "D4:8"},
    )
    lookup_row = EpisodicItem(
        id=uuid.uuid4(),
        project_id=project_id,
        source="benchmark",
        text="Melanie: museum trip",
        metadata_={"dia_id": "D4:8"},
    )
    db.execute.return_value.scalars.return_value.all.side_effect = [
        [lookup_row],
        [turn_d6, turn_d4],
    ]

    context = ["[observation D6:6] Melanie enjoys time with her kids."]
    merged, _ = router._hydrate_source_turns(
        project_id, context, ["obs-1"], query=query
    )
    joined = "\n".join(merged)
    assert "[source turn D6:6]" in joined
    assert "[source turn D4:8]" in joined


def test_hydrate_source_turns_skips_when_no_observation_ids():
    db = MagicMock()
    router = MemoryRouter(db, MagicMock())
    context = ["Assertion: Bob likes cats (conf: 0.9)"]
    sources = ["a1"]
    merged, merged_sources = router._hydrate_source_turns(uuid.uuid4(), context, sources)
    assert merged == context
    assert merged_sources == sources
    db.execute.assert_not_called()
