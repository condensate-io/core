import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from src.db.models import Assertion, Entity, EpisodicItem, Policy, Relation
from src.engine.condenser import Condenser


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
        for call in mock_db.add_all.call_args_list:
            added_objects.extend(call[0][0])

        found_entity = any(isinstance(obj, Entity) and "v2.0" in obj.canonical_name for obj in added_objects)
        found_summary = any(isinstance(obj, Assertion) and obj.predicate == "summarized_as" for obj in added_objects)

        assert found_entity, "Should have created an Entity for v2.0"
        assert found_summary, "Should have created a summary Assertion"
        mock_db.commit.assert_called()


@pytest.mark.asyncio
async def test_condenser_skips_ner_for_code_artifacts(mock_db):
    """Codebase items should bypass GLiNER NER and use the code-aware
    DeterministicCondenser fast path instead (perf: no model inference)."""
    with patch("src.engine.condenser.get_ner_engine") as mock_get_ner, \
         patch("src.engine.condenser.get_thread_shard") as mock_get_shard:

        mock_ner_instance = MagicMock()
        mock_ner_instance.extract_entities.return_value = []
        mock_get_ner.return_value = mock_ner_instance

        mock_shard_instance = MagicMock()

        def mock_submit(fn, *args, **kwargs):
            from concurrent.futures import Future
            f = Future()
            f.set_result(fn(*args, **kwargs))
            return f

        mock_shard_instance.submit.side_effect = mock_submit
        mock_get_shard.return_value = mock_shard_instance

        condenser = Condenser(mock_db)

        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        mock_db.execute.return_value.scalars.return_value.first.return_value = None

        project_id = uuid4()
        items = [
            EpisodicItem(
                id=uuid4(),
                text="import os\n\nclass Widget:\n    def run(self):\n        pass\n",
                source="codebase",
                metadata_={"source": "codebase", "extension": ".py"},
            )
        ]

        with patch.dict(os.environ, {"LLM_ENABLED": "false"}):
            await condenser.distill(project_id, items)

        # NER should never be invoked for a batch made entirely of code items.
        mock_ner_instance.extract_entities.assert_not_called()

        added_objects = [call[0][0] for call in mock_db.add.call_args_list]
        for call in mock_db.add_all.call_args_list:
            added_objects.extend(call[0][0])

        found_symbol = any(
            isinstance(obj, Entity) and obj.canonical_name == "Widget"
            for obj in added_objects
        )
        assert found_symbol, "Should have created an Entity for the Widget class"


@pytest.mark.asyncio
async def test_condenser_runs_ner_for_codebase_markdown(mock_db):
    with patch("src.engine.condenser.get_ner_engine") as mock_get_ner, \
         patch("src.engine.condenser.get_thread_shard") as mock_get_shard:

        mock_ner_instance = MagicMock()
        mock_ner_instance.extract_entities.return_value = []
        mock_get_ner.return_value = mock_ner_instance

        mock_shard_instance = MagicMock()

        def mock_submit(fn, *args, **kwargs):
            from concurrent.futures import Future
            f = Future()
            f.set_result(fn(*args, **kwargs))
            return f

        mock_shard_instance.submit.side_effect = mock_submit
        mock_get_shard.return_value = mock_shard_instance

        condenser = Condenser(mock_db)

        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        mock_db.execute.return_value.scalars.return_value.first.return_value = None

        item = EpisodicItem(
            id=uuid4(),
            text="# README\nAcme uses Widget for deploys.\n",
            source="codebase",
            metadata_={"source": "codebase", "extension": ".md"},
        )

        with patch.dict(os.environ, {"LLM_ENABLED": "false"}):
            await condenser.distill(uuid4(), [item])

        mock_ner_instance.extract_entities.assert_called_once()
