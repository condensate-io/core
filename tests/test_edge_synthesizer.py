import pytest
import uuid
from unittest.mock import MagicMock
from src.engine.edge_synthesizer import EdgeSynthesizer
from src.db.models import Relation

@pytest.fixture
def mock_db():
    return MagicMock()

def test_synthesize_creates_bidirectional_edges(mock_db):
    synth = EdgeSynthesizer(mock_db)
    project_id = uuid.uuid4()
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()

    # Mock no existing relations (single batched SELECT returns nothing)
    mock_db.execute.return_value.scalars.return_value.all.return_value = []

    batch_prov = {"batch_ts": "2026-02-18T00:00:00"}

    # Synthesize between 2 entities
    count = synth.synthesize(project_id, [id1, id2], batch_prov)

    # Should create 2 edges (A->B and B->A)
    assert count == 2
    # New relations are added in a single bulk add_all call
    assert mock_db.add_all.call_count == 1
    new_relations = mock_db.add_all.call_args[0][0]
    assert len(new_relations) == 2

    # Verify first edge
    rel1 = new_relations[0]
    assert isinstance(rel1, Relation)
    assert rel1.from_id == id1
    assert rel1.to_id == id2
    assert rel1.relation_type == "co_occurs_with"
    assert rel1.strength == 1.0

def test_synthesize_reinforces_existing_edges(mock_db):
    synth = EdgeSynthesizer(mock_db)
    project_id = uuid.uuid4()
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()

    # Mock existing relation (only the A->B direction exists in DB)
    existing_rel = Relation(
        from_id=id1, to_id=id2, strength=1.0, access_count=1, provenance=[]
    )
    mock_db.execute.return_value.scalars.return_value.all.return_value = [existing_rel]

    batch_prov = {"batch_ts": "2026-02-18T00:00:01"}

    # Run synthesis
    count = synth.synthesize(project_id, [id1, id2], batch_prov)

    assert count == 2
    # Strength should increase for the existing edge
    assert existing_rel.strength > 1.0
    assert existing_rel.access_count == 2
    assert len(existing_rel.provenance) == 1
    assert existing_rel.provenance[0]["batch_ts"] == "2026-02-18T00:00:01"

    # The reverse direction (B->A) didn't exist, so exactly one new relation
    # should be bulk-added.
    assert mock_db.add_all.call_count == 1
    new_relations = mock_db.add_all.call_args[0][0]
    assert len(new_relations) == 1
    assert new_relations[0].from_id == id2
    assert new_relations[0].to_id == id1

def test_synthesize_requires_at_least_two_entities(mock_db):
    synth = EdgeSynthesizer(mock_db)
    count = synth.synthesize(uuid.uuid4(), [uuid.uuid4()], {})
    assert count == 0
    assert mock_db.add_all.call_count == 0


def test_synthesize_caps_entities_per_batch(mock_db, monkeypatch):
    monkeypatch.setenv("EDGE_SYNTH_MAX_ENTITIES", "3")
    mock_db.execute.return_value.scalars.return_value.all.return_value = []

    synth = EdgeSynthesizer(mock_db)
    project_id = uuid.uuid4()
    entity_ids = [uuid.uuid4() for _ in range(10)]

    count = synth.synthesize(project_id, entity_ids, {"batch_ts": "x"})

    # With a cap of 3 entities: 3 pairs * 2 directions = 6 edges
    assert count == 6
