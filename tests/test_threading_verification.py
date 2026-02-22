
import sys
import asyncio
import time
import uuid
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy.orm import Session

# Standalone function to bypass pickling issues with Mapped (though pickling isn't used here)
def standalone_heavy_computation(text):
    time.sleep(0.1)  # Simulate 100ms work
    return [{"text": "entity", "label": "concept", "score": 0.9, "start": 0, "end": 0}]

def standalone_guardrail_check(text):
    time.sleep(0.1) # Simulate 100ms work
    return {
        "should_block": False,
        "instruction_matches": [],
        "safety_matches": [],
        "instruction_score": 0.0,
        "safety_score": 0.0
    }

@pytest.mark.asyncio
async def test_run_verification():
    print("Starting verification of threading optimization...")

    # We use patch.dict or context managers to ensure these don't leak
    with patch.dict(sys.modules, {
        'src.engine.guardrails': MagicMock(),
        'src.engine.ner': MagicMock(),
        'src.learn.canonicalize': MagicMock(),
        'src.engine.edge_synthesizer': MagicMock(),
        'fastembed': MagicMock()
    }):
        # Now import project modules within the patch context
        from src.engine.condenser import Condenser
        from src.db.models import EpisodicItem
        from src.engine.thread_shard import get_thread_shard

        # Setup DB Mock
        db = MagicMock(spec=Session)
        db.execute.return_value.scalar_one_or_none.return_value = None

        # Init Condenser
        condenser = Condenser(db)
        
        # Configure dependencies
        condenser.ner.extract_entities = standalone_heavy_computation

        # For GuardrailEngine:
        gw_class_mock = sys.modules['src.engine.guardrails'].GuardrailEngine
        gw_instance_mock = gw_class_mock.return_value
        gw_instance_mock.check = standalone_guardrail_check
        
        # Create Test Data
        num_items = 5
        items = []
        for i in range(num_items):
            items.append(EpisodicItem(
                id=uuid.uuid4(),
                text=f"This is item {i} with some entities.",
                project_id=uuid.uuid4(),
                source="test"
            ))

        # Measure Execution Time
        start_time = time.time()
        
        # Mock DeterministicCondenser and MemoryExtractor to avoid timeouts and LLM calls
        with patch('src.engine.deterministic.DeterministicCondenser') as MockDC, \
             patch('src.learn.extractor.MemoryExtractor.extract') as MockExtract:
            
            dc_instance = MockDC.return_value
            dc_instance.process.return_value = {
                "entities": [],
                "condensed": "Summary of batch"
            }
            
            # Mock extractor to return empty bundles immediately
            MockExtract.return_value = asyncio.Future()
            MockExtract.return_value.set_result([])
            
            print("Calling condenser.distill...")
            await condenser.distill(items[0].project_id, items)
            print("Returned from condenser.distill.")

        end_time = time.time()
        duration = end_time - start_time
        
        print(f"Processed {num_items} items in {duration:.4f} seconds.")
        
        if duration < 0.6:
            print("SUCCESS: Performance indicates parallel execution.")
        else:
            print("WARNING: Execution time suggests potential serialization or high overhead.")
            print(f"Expected < 0.6s, got {duration:.4f}s")

    # Cleanup shard
    get_thread_shard().shutdown()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(test_run_verification())
    finally:
        loop.close()
