import httpx
import uuid
from typing import Optional, Dict, Any
from .types import EpisodicItem, RetrieveRequest, RetrieveResponse

class CondensateClient:
    def __init__(self, base_url: str = "http://localhost:8000", api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}" if api_key else ""
        }
        self.client = httpx.Client(base_url=self.base_url, headers=self.headers, timeout=30.0)

    def add_item(self, text: str = None, source: str = "api", item: EpisodicItem = None, **kwargs) -> str:
        """
        Ingest a raw memory item.
        
        Args:
            text: Simple text content (convenience)
            source: Source identifier (default: "api")
            item: Full EpisodicItem object (alternative to text/source)
            **kwargs: Additional fields for EpisodicItem
            
        Returns:
            The ID of the created item.
        """
        if item is None:
            if "project_id" not in kwargs or kwargs["project_id"] is None:
                kwargs["project_id"] = uuid.UUID("00000000-0000-0000-0000-000000000000")
            item = EpisodicItem(text=text, source=source, **kwargs)
        elif item.project_id is None:
            item.project_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        
        # Convert to dict for JSON serialization
        payload = item.model_dump(mode='json')
        resp = self.client.post("/api/v1/episodic", json=payload)
        resp.raise_for_status()
        return resp.json()["id"]

    def add_lifecycle_event(self, event_type: str, task_id: str, agent_id: str, text: str, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        """
        Standardize injection of event_type metadata for Symphony-like orchestrations.
        """
        full_metadata = {
            "event_type": event_type,
            "task_id": task_id,
            "agent_id": agent_id,
            **(metadata or {})
        }
        return self.add_item(text=text, source="orchestrator", metadata=full_metadata, **kwargs)

    def retrieve(self, query: str, project_id: Optional[str] = None, skip_llm: bool = False) -> Dict[str, Any]:
        """
        Retrieve knowledge based on a query.
        
        Args:
            query: The search query
            project_id: Optional project scope
            skip_llm: Skip LLM synthesis (default: False)
            
        Returns:
            Dictionary with 'answer' and 'context' keys
        """
        payload = {
            "query": query,
            "project_id": project_id,
            "skip_llm": skip_llm
        }
        # Filter None values
        payload = {k: v for k, v in payload.items() if v is not None}
        
        resp = self.client.post("/api/v1/memory/retrieve", json=payload)
        resp.raise_for_status()
        return resp.json()
        
    def close(self):
        self.client.close()
