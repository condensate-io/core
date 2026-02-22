import pytest
import uuid
from datetime import datetime
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
    
    # Mock no existing relations
    mock_db.execute.return_value.scalars.return_value.first.return_value = None
    
    batch_prov = {"batch_ts": "2026-02-18T00:00:00"}
    
    # Synthesize between 2 entities
    count = synth.synthesize(project_id, [id1, id2], batch_prov)
    
    # Should create 2 edges (A->B and B->A)
    assert count == 2
    assert mock_db.add.call_count == 2
    
    # Verify first edge
    rel1 = mock_db.add.call_args_list[0][0][0]
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
    
    # Mock existing relation
    existing_rel = Relation(
        from_id=id1, to_id=id2, strength=1.0, access_count=1, provenance=[]
    )
    mock_db.execute.return_value.scalars.return_value.first.return_value = existing_rel
    
    batch_prov = {"batch_ts": "2026-02-18T00:00:01"}
    
    # Run synthesis
    synth.synthesize(project_id, [id1, id2], batch_prov)
    
    # Strength should increase
    assert existing_rel.strength > 1.0
    # access_count starts at 1. Bidirectional synthesis reinforces twice (A->B and B->A).
    # Since our mock returns the same object for both directions, it increments twice.
    assert existing_rel.access_count == 3
    assert len(existing_rel.provenance) == 1
    assert existing_rel.provenance[0]["batch_ts"] == "2026-02-18T00:00:01"

def test_synthesize_requires_at_least_two_entities(mock_db):
    synth = EdgeSynthesizer(mock_db)
    count = synth.synthesize(uuid.uuid4(), [uuid.uuid4()], {})
    assert count == 0
    assert mock_db.add.call_count == 0
