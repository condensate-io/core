import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from src.db.models import Assertion, Entity, EpisodicItem
from src.learn.canonicalize import EntityCanonicalizer
from src.learn.consolidate import KnowledgeConsolidator
from src.llm.schemas import ExtractedAssertion, ExtractedEntity, ExtractionBundle


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
    # New entities are bulk-added in a single add_all call
    assert mock_db.add_all.call_count == 1
    added_entities = mock_db.add_all.call_args[0][0]
    assert len(added_entities) == 2


def test_canonicalizer_query_normalizes_sql_lookup(mock_db):
    canon = EntityCanonicalizer(mock_db)
    project_id = str(uuid.uuid4())
    mock_db.execute.return_value.scalars.return_value.all.return_value = []

    canon.resolve(
        project_id,
        [ExtractedEntity(name="foo", type="concept", aliases=["Bar"], confidence=1.0)],
    )

    stmt = mock_db.execute.call_args_list[0][0][0]
    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert "regexp_replace" in compiled
    assert "jsonb_array_elements_text" in compiled

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

    # Mock no existing duplicates or conflicts
    mock_db.execute.return_value.scalars.return_value.first.return_value = None
    mock_db.execute.return_value.scalars.return_value.all.return_value = []

    con.consolidate(project_id, assertions, entity_map)

    # Verify add
    assert mock_db.add.call_count == 1
    args = mock_db.add.call_args[0][0]
    assert isinstance(args, Assertion)
    assert args.predicate == "knows"
