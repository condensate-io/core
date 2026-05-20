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
    api_key_name: Optional[str] = None

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

class EntityCreate(BaseModel):
    project_id: uuid.UUID
    name: str
    type: str # person|org|system|project|tool|concept|artifact|other
    aliases: Optional[List[str]] = None
    confidence: Optional[float] = 1.0

class EntityResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    type: str
    aliases: List[str]
    confidence: float
    
    model_config = ConfigDict(from_attributes=True)

class AssertionResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    subject_entity_id: Optional[uuid.UUID]
    subject_text: Optional[str]
    predicate: str
    object_entity_id: Optional[uuid.UUID]
    object_text: Optional[str]
    polarity: int
    confidence: float
    status: str
    temporal_step: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(from_attributes=True)

class RelationCreate(BaseModel):
    project_id: uuid.UUID
    from_id: uuid.UUID
    from_kind: Optional[str] = "entity" # entity|ontology
    to_id: uuid.UUID
    to_kind: Optional[str] = "entity" # entity|ontology
    relation_type: str
    confidence: Optional[float] = 1.0

class RelationResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    from_id: uuid.UUID
    from_kind: str
    relation_type: str
    to_id: uuid.UUID
    to_kind: str
    confidence: float
    temporal_start: Optional[int] = None
    temporal_end: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(from_attributes=True)

class OntologyNodeCreate(BaseModel):
    label: str
    node_type: str # entity_type|edge_type|concept|category|schema

class OntologyCreate(BaseModel):
    project_id: Optional[uuid.UUID] = None
    entity_types: Optional[List[str]] = []
    edge_types: Optional[List[str]] = []

class OntologyNodeResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    label: str
    node_type: str
    parent_ids: List[str]
    confidence: float
    
    model_config = ConfigDict(from_attributes=True)

class EpisodicBulkCreate(BaseModel):
    project_id: uuid.UUID
    episodes: List[EpisodicItemCreate]

class GraphCreate(BaseModel):
    project_id: Optional[uuid.UUID] = None
    name: str
    api_key_name: Optional[str] = None
