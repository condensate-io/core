from typing import Dict, Any, Optional
from .client import CondensateClient

class CondensateOrchestrationHooks:
    """
    Helper class to emit lifecycle hooks for Symphony-like orchestrations.
    All events are emitted to the `/api/v1/episodic` endpoint and tagged
    via metadata["event_type"] for tenant isolation and clean analysis.
    """
    def __init__(self, client: CondensateClient):
        self.client = client

    def on_agent_started(self, task_id: str, agent_id: str, agent_role: str = "developer") -> str:
        """
        Log the start of an autonomous agent execution session.
        """
        text = f"Lifecycle Event: Task {task_id} started by agent {agent_id} ({agent_role})"
        metadata = {
            "event_type": "lifecycle_start",
            "task_id": task_id,
            "agent_id": agent_id,
            "agent_role": agent_role
        }
        return self.client.add_item(text=text, source="orchestrator", metadata=metadata)

    def on_agent_suspended(self, task_id: str, agent_id: str, state_dump: Dict[str, Any]) -> str:
        """
        Log agent suspension, checkpointing its current execution state for resume/hand-off.
        """
        text = f"Lifecycle Event: Task {task_id} suspended by agent {agent_id} (checkpoint saved)"
        metadata = {
            "event_type": "lifecycle_suspend",
            "task_id": task_id,
            "agent_id": agent_id,
            "state_dump": state_dump
        }
        return self.client.add_item(text=text, source="orchestrator", metadata=metadata)

    def on_agent_resumed(self, task_id: str, agent_id: str) -> str:
        """
        Log agent resumption.
        """
        text = f"Lifecycle Event: Task {task_id} resumed by agent {agent_id}"
        metadata = {
            "event_type": "lifecycle_resume",
            "task_id": task_id,
            "agent_id": agent_id
        }
        return self.client.add_item(text=text, source="orchestrator", metadata=metadata)

    def on_agent_crashed(self, task_id: str, agent_id: str, error: str, state_dump: Optional[Dict[str, Any]] = None) -> str:
        """
        Log agent crash for fault tolerance tracing and recovery.
        """
        text = f"Lifecycle Event: Task {task_id} crashed for agent {agent_id}. Error: {error}"
        metadata = {
            "event_type": "lifecycle_crash",
            "task_id": task_id,
            "agent_id": agent_id,
            "error": error,
        }
        if state_dump:
            metadata["state_dump"] = state_dump
        return self.client.add_item(text=text, source="orchestrator", metadata=metadata)

    def on_agent_completed(self, task_id: str, agent_id: str, final_findings: str) -> str:
        """
        Log task completion, summarizing findings for future agent hand-offs.
        """
        text = f"Lifecycle Event: Task {task_id} completed by agent {agent_id}. Findings: {final_findings}"
        metadata = {
            "event_type": "lifecycle_complete",
            "task_id": task_id,
            "agent_id": agent_id,
            "final_findings": final_findings
        }
        return self.client.add_item(text=text, source="orchestrator", metadata=metadata)
