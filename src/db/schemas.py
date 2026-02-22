from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

class EpisodicItemCreate(BaseModel):
    project_id: str
    source: str = "api" # chatgpt_export|api|tool|note
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    occurred_at: Optional[datetime] = None

class EpisodicItemResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    source: str
    text: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ProjectCreate(BaseModel):
    name: str

class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class LearningCreate(BaseModel):
    statement: str
    confidence: float
    evidence_ids: List[str] # List of Memory IDs

class DataSourceCreate(BaseModel):
    name: str
    source_type: str
    configuration: Dict[str, Any]
    cron_schedule: Optional[str] = None
    enabled: bool = True

class DataSourceResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    source_type: str
    configuration: Dict[str, Any]
    cron_schedule: Optional[str]
    enabled: bool
    last_run: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
