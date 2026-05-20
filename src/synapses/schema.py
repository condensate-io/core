from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

class SynapseBase(BaseModel):
    from_memory_id: uuid.UUID
    to_memory_id: uuid.UUID
    relation_type: str
    weight: float = 1.0
    evidence_ids: List[uuid.UUID] = Field(default_factory=list)
    created_by: str = "condenser" # condenser|retrieval|consolidation
    decay_rate: float = 0.995

class SynapseCreate(SynapseBase):
    pass

class SynapseResponse(SynapseBase):
    id: uuid.UUID
    last_activated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class SynapseActivationBase(BaseModel):
    synapse_id: uuid.UUID
    relevance_score: float
    context_query: Optional[str] = None

class SynapseActivationCreate(SynapseActivationBase):
    pass

class SynapseActivationResponse(SynapseActivationBase):
    id: uuid.UUID
    activated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ConsolidatedMemoryBase(BaseModel):
    project_id: uuid.UUID
    content: str
    evidence_ids: List[uuid.UUID]
    confidence: float

class ConsolidatedMemoryCreate(ConsolidatedMemoryBase):
    pass

class ConsolidatedMemoryResponse(ConsolidatedMemoryBase):
    id: uuid.UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
