
import asyncio
import uuid
from unittest.mock import MagicMock, patch
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.getcwd()))

from src.engine.condenser import Condenser
from src.db.models import EpisodicItem

async def repro():
    print("[Repro] Setting up mocks...")
    mock_db = MagicMock()
    # Mock DB executes
    mock_db.execute.return_value.scalars.return_value.all.return_value = []
    mock_db.execute.return_value.scalar_one_or_none.return_value = None
    mock_db.execute.return_value.scalars.return_value.first.return_value = None

    with patch("src.engine.condenser.get_ner_engine") as mock_get_ner, \
         patch("src.engine.condenser.get_thread_shard") as mock_get_shard:
        
        # Mock NER
        mock_ner_instance = MagicMock()
        mock_ner_instance.extract_entities.return_value = []
        mock_get_ner.return_value = mock_ner_instance
        
        # Mock Shard
        mock_shard_instance = MagicMock()
        def mock_submit(fn, *args, **kwargs):
            from concurrent.futures import Future
            print(f"[Repro] Shard.submit called for {fn}")
            f = Future()
            f.set_result(fn(*args, **kwargs))
            return f
        mock_shard_instance.submit.side_effect = mock_submit
        mock_get_shard.return_value = mock_shard_instance
        
        print("[Repro] Initializing Condenser...")
        condenser = Condenser(mock_db)
        
        project_id = uuid.uuid4()
        items = [
            EpisodicItem(id=uuid.uuid4(), text="We need to prioritize the v2.0 migration.", source="chat")
        ]
        
        # Patch DeterministicCondenser path too just in case
        with patch.dict(os.environ, {"LLM_ENABLED": "false"}):
            print("[Repro] Calling distill...")
            await condenser.distill(project_id, items)
            print("[Repro] Distill returned.")

if __name__ == "__main__":
    asyncio.run(repro())
