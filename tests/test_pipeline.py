import pytest
from unittest.mock import MagicMock, AsyncMock
from src.db.models import EpisodicItem, Entity, Assertion
from src.llm.schemas import ExtractionBundle, ExtractedEntity, ExtractedAssertion
from src.learn.canonicalize import EntityCanonicalizer
from src.learn.consolidate import KnowledgeConsolidator
import uuid

@pytest.fixture
def mock_db():
    session = MagicMock()
    return session

def test_canonicalizer(mock_db):
    # Setup
    canon = EntityCanonicalizer(mock_db)
    project_id = str(uuid.uuid4())
    
    # Mock existing entities
    mock_db.execute.return_value.scalars.return_value.all.return_value = []
    
    # Input
    extracted = [
        ExtractedEntity(name="Bob Smith", type="person", aliases=["Bob"], confidence=1.0),
        ExtractedEntity(name="Alice", type="person", aliases=[], confidence=0.9)
    ]
    
    # Run
    mapping = canon.resolve(project_id, extracted)
    
    # Verify
    assert "Bob Smith" in mapping
    assert "Alice" in mapping
    # Should have added 2 entities to DB
    assert mock_db.add.call_count == 2

def test_consolidator(mock_db):
    con = KnowledgeConsolidator(mock_db)
    project_id = str(uuid.uuid4())
    entity_map = {"Bob": str(uuid.uuid4()), "Alice": str(uuid.uuid4())}
    
    assertions = [
        ExtractedAssertion(
            subject={"type": "entity", "name": "Bob"},
            predicate="knows",
            object={"type": "entity", "name": "Alice"},
            confidence=0.9
        )
    ]
    
    # Mock no existing
    mock_db.execute.return_value.scalars.return_value.first.return_value = None
    
    con.consolidate(project_id, assertions, entity_map)
    
    # Verify add
    assert mock_db.add.call_count == 1
    args = mock_db.add.call_args[0][0]
    assert isinstance(args, Assertion)
    assert args.predicate == "knows"
