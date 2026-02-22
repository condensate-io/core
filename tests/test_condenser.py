import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import asyncio
from uuid import uuid4
from unittest.mock import MagicMock, patch
from src.engine.condenser import Condenser
from src.db.models import EpisodicItem, Assertion, Policy, Entity, Relation

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.mark.asyncio
async def test_condenser_distills_relationships(mock_db):
    # Patch get_ner_engine to return a mock
    # Patch get_thread_shard to return a synchronous mock
    with patch("src.engine.condenser.get_ner_engine") as mock_get_ner, \
         patch("src.engine.condenser.get_thread_shard") as mock_get_shard:
        
        # Mock NER
        mock_ner_instance = MagicMock()
        mock_ner_instance.extract_entities.return_value = []
        mock_get_ner.return_value = mock_ner_instance
        
        # Mock Shard (Synchronous execution)
        mock_shard_instance = MagicMock()
        def mock_submit(fn, *args, **kwargs):
            from concurrent.futures import Future
            f = Future()
            f.set_result(fn(*args, **kwargs))
            return f
        mock_shard_instance.submit.side_effect = mock_submit
        mock_get_shard.return_value = mock_shard_instance
        
        condenser = Condenser(mock_db)
        
        # Mock DB executes for canonicalization and relations
        # We need to return an empty list for scalars().all() during entity lookup
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        # Return None for scalar_one_or_none in _create_assertion
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        # For EdgeSynthesizer, return None for existing relation
        mock_db.execute.return_value.scalars.return_value.first.return_value = None
        
        project_id = uuid4()
        # "v2.0" and "migration" should be detected as entities by DeterministicCondenser
        items = [
            EpisodicItem(id=uuid4(), text="We need to prioritize the v2.0 migration.", source="chat")
        ]
        
        # Force deterministic path regardless of container env var
        with patch.dict(os.environ, {"LLM_ENABLED": "false"}):
            print("[Test] Calling condenser.distill...")
            await condenser.distill(project_id, items)
            print("[Test] condenser.distill returned.")
        
        # Verify DB actions
        added_objects = [call[0][0] for call in mock_db.add.call_args_list]
        
        found_entity = any(isinstance(obj, Entity) and "v2.0" in obj.canonical_name for obj in added_objects)
        found_summary = any(isinstance(obj, Assertion) and obj.predicate == "summarized_as" for obj in added_objects)
        
        assert found_entity, "Should have created an Entity for v2.0"
        assert found_summary, "Should have created a summary Assertion"
        mock_db.commit.assert_called()
