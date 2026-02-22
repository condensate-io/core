from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

class EpisodicItem(BaseModel):
    project_id: uuid.UUID
    source: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    occurred_at: Optional[datetime] = None

class RetrieveRequest(BaseModel):
    query: str
    project_id: Optional[uuid.UUID] = None
    limit: int = 5
    filters: Dict[str, Any] = Field(default_factory=dict)

class RetrieveResponse(BaseModel):
    answer: str
    context: List[Dict[str, Any]]
