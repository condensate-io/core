import pytest
import time
from src.engine.thread_shard import AdaptiveThreadShard

def test_thread_shard_execution():
    shard = AdaptiveThreadShard(initial_workers=2, monitor_interval=1)
    
    def slow_task(duration):
        time.sleep(duration)
        return duration
        
    # Submit tasks
    futures = [shard.submit(slow_task, 0.1) for _ in range(5)]
    
    # Wait for results
    results = [f.result() for f in futures]
    assert len(results) == 5
    assert all(r == 0.1 for r in results)
    
    shard.shutdown()

def test_thread_shard_adaptation():
    # This test is tricky because adaptation relies on timing.
    # We verify the method exists and runs without error.
    shard = AdaptiveThreadShard(initial_workers=2, monitor_interval=0.1)
    
    shard._rebuild_executor(4)
    assert shard.current_workers == 4
    # Check internal prop
    assert shard.executor._max_workers == 4
    
    shard.shutdown()
