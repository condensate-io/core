import os
import time
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from src.db.models import EpisodicItem


def standalone_heavy_computation(text, labels=None):
    """Simulate CPU-bound NER without loading models."""
    time.sleep(0.05)
    return [{"text": "entity", "label": "concept", "score": 0.9, "start": 0, "end": 0}]


@pytest.mark.asyncio
async def test_run_verification():
    mock_ner = MagicMock()
    mock_ner.DEFAULT_LABELS = ["person", "org"]
    mock_ner.extract_entities = MagicMock(side_effect=standalone_heavy_computation)

    mock_shard = MagicMock()

    def mock_submit(fn, *args, **kwargs):
        from concurrent.futures import Future

        future = Future()
        future.set_result(fn(*args, **kwargs))
        return future

    mock_shard.submit.side_effect = mock_submit

    db = MagicMock(spec=Session)
    db.execute.return_value.scalars.return_value.all.return_value = []
    db.execute.return_value.scalar_one_or_none.return_value = None
    db.execute.return_value.scalars.return_value.first.return_value = None

    num_items = 5
    project_id = uuid.uuid4()
    items = [
        EpisodicItem(
            id=uuid.uuid4(),
            text=f"This is item {i} with some entities.",
            project_id=project_id,
            source="test",
        )
        for i in range(num_items)
    ]

    with patch("src.engine.condenser.get_ner_engine", return_value=mock_ner), \
         patch("src.engine.condenser.get_thread_shard", return_value=mock_shard), \
         patch("src.engine.deterministic.DeterministicCondenser") as mock_dc_cls, \
         patch("src.engine.guardrails.GuardrailEngine") as mock_gw, \
         patch.dict(os.environ, {"LLM_ENABLED": "false"}):
        mock_dc_cls.return_value.process.return_value = {
            "entities": [],
            "condensed": "Summary of batch",
            "facts": [],
        }
        mock_gw.return_value.check.return_value = {
            "should_block": False,
            "instruction_score": 0.0,
            "safety_score": 0.0,
            "instruction_matches": [],
            "safety_matches": [],
        }

        from src.engine.condenser import Condenser

        condenser = Condenser(db)
        start = time.time()
        await condenser.distill(project_id, items)
        duration = time.time() - start

    assert mock_ner.extract_entities.call_count == num_items
    assert duration < 2.0, (
        f"distill took {duration:.2f}s — likely triggered real model download"
    )
