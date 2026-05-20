import pytest
from unittest.mock import MagicMock
from sdks.python.condensate.client import CondensateClient
from sdks.python.condensate.lifecycle import CondensateOrchestrationHooks

def test_sdk_lifecycle_hooks_serialization():
    # 1. Create a mocked client
    mock_client = MagicMock(spec=CondensateClient)
    mock_client.add_item.return_value = "item-123"

    # 2. Instantiate hooks
    hooks = CondensateOrchestrationHooks(mock_client)

    # 3. Test on_agent_started
    res_started = hooks.on_agent_started(task_id="task-1", agent_id="agent-abc", agent_role="orchestrator")
    assert res_started == "item-123"
    mock_client.add_item.assert_called_once_with(
        text="Lifecycle Event: Task task-1 started by agent agent-abc (orchestrator)",
        source="orchestrator",
        metadata={
            "event_type": "lifecycle_start",
            "task_id": "task-1",
            "agent_id": "agent-abc",
            "agent_role": "orchestrator"
        }
    )
    mock_client.add_item.reset_mock()

    # 4. Test on_agent_suspended
    state_dump = {"current_file": "main.py", "progress": 0.5}
    res_suspended = hooks.on_agent_suspended(task_id="task-1", agent_id="agent-abc", state_dump=state_dump)
    assert res_suspended == "item-123"
    mock_client.add_item.assert_called_once_with(
        text="Lifecycle Event: Task task-1 suspended by agent agent-abc (checkpoint saved)",
        source="orchestrator",
        metadata={
            "event_type": "lifecycle_suspend",
            "task_id": "task-1",
            "agent_id": "agent-abc",
            "state_dump": state_dump
        }
    )
    mock_client.add_item.reset_mock()

    # 5. Test on_agent_resumed
    res_resumed = hooks.on_agent_resumed(task_id="task-1", agent_id="agent-abc")
    assert res_resumed == "item-123"
    mock_client.add_item.assert_called_once_with(
        text="Lifecycle Event: Task task-1 resumed by agent agent-abc",
        source="orchestrator",
        metadata={
            "event_type": "lifecycle_resume",
            "task_id": "task-1",
            "agent_id": "agent-abc"
        }
    )
    mock_client.add_item.reset_mock()

    # 6. Test on_agent_crashed
    error_msg = "Database Connection Timeout"
    res_crashed = hooks.on_agent_crashed(task_id="task-1", agent_id="agent-abc", error=error_msg, state_dump=state_dump)
    assert res_crashed == "item-123"
    mock_client.add_item.assert_called_once_with(
        text="Lifecycle Event: Task task-1 crashed for agent agent-abc. Error: Database Connection Timeout",
        source="orchestrator",
        metadata={
            "event_type": "lifecycle_crash",
            "task_id": "task-1",
            "agent_id": "agent-abc",
            "error": error_msg,
            "state_dump": state_dump
        }
    )
    mock_client.add_item.reset_mock()

    # 7. Test on_agent_completed
    findings = "Found 3 active security leaks and patched them."
    res_completed = hooks.on_agent_completed(task_id="task-1", agent_id="agent-abc", final_findings=findings)
    assert res_completed == "item-123"
    mock_client.add_item.assert_called_once_with(
        text="Lifecycle Event: Task task-1 completed by agent agent-abc. Findings: Found 3 active security leaks and patched them.",
        source="orchestrator",
        metadata={
            "event_type": "lifecycle_complete",
            "task_id": "task-1",
            "agent_id": "agent-abc",
            "final_findings": findings
        }
    )
