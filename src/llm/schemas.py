from typing import List, Optional, Any, Literal
from pydantic import BaseModel, Field, UUID4, field_validator, model_validator
import uuid

# --- Extraction Schemas (LLM Output) ---

# Mapping of known LLM abbreviations/variants -> canonical type
_ENTITY_TYPE_NORMALIZER = {
    # NER model labels (dslim/bert-base-NER returns PER, ORG, LOC, MISC)
    "per": "person",
    "PER": "person",
    "person": "person",
    "people": "person",
    "human": "person",
    "individual": "person",
    "ORG": "org",
    "org": "org",
    "organisation": "org",
    "organization": "org",
    "company": "org",
    "LOC": "concept",   # location -> concept (no 'location' type exists)
    "loc": "concept",
    "location": "concept",
    "place": "concept",
    "MISC": "other",
    "misc": "other",
    "system": "system",
    "project": "project",
    "tool": "tool",
    "concept": "concept",
    "artifact": "artifact",
    "other": "other",
}

class ExtractedEntity(BaseModel):
    name: str = Field(..., description="Canonical name of the entity")
    type: Literal["person", "org", "system", "project", "tool", "concept", "artifact", "other"]
    aliases: List[str] = Field(default_factory=list, description="Known aliases for this entity")
    confidence: float = Field(0.8, ge=0.0, le=1.0)

    @model_validator(mode="before")
    @classmethod
    def robust_parsing(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Recovery for missing 'name' if 'references' or 'value' exists
            if not data.get("name"):
                if data.get("references"):
                    data["name"] = str(data.get("references", [""])[0])
                elif data.get("aliases"):
                    data["name"] = str(data.get("aliases", [""])[0])
                elif data.get("value"):
                    data["name"] = str(data.get("value"))
            
            # Recovery for missing 'type' if 'label' or 'category' or 'kind' exists
            if not data.get("type"):
                if data.get("label"):
                    data["type"] = data.get("label")
                elif data.get("category"):
                    data["type"] = data.get("category")
                elif data.get("kind"):
                    data["type"] = data.get("kind")
                    
            # Default confidence if LLM omits it
            if "confidence" not in data or data["confidence"] is None:
                data["confidence"] = 0.8
        return data

    @field_validator("type", mode="before")
    @classmethod
    def normalize_entity_type(cls, v: Any) -> str:
        """Normalize LLM abbreviations and NER model labels to valid entity types."""
        if isinstance(v, str):
            normalized = _ENTITY_TYPE_NORMALIZER.get(v) or _ENTITY_TYPE_NORMALIZER.get(v.lower())
            if normalized:
                return normalized
        return v  # Let Pydantic's Literal validation handle the error if still invalid

class AssertionEvidence(BaseModel):
    episodic_id: UUID4
    quote: str = Field(..., max_length=240)

class ExtractedAssertion(BaseModel):
    subject: Any = Field(..., description="Entity dict or literal value") 
    # subject can be {"type": "entity", "name": "..."} or {"type": "literal", "value": "..."}
    predicate: str = Field(..., description="Relationship verb (prefers, uses, etc)")
    object: Any = Field(..., description="Entity dict or literal value")
    polarity: int = Field(1, description="1 for affirm, -1 for negated")
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: List[AssertionEvidence] = Field(default_factory=list)

class ExtractedEvent(BaseModel):
    type: str # meeting, decision, etc
    summary: str
    occurred_at: Optional[str] = None # ISO8601
    participants: List[Any] = Field(default_factory=list) # Entity references
    attributes: dict = Field(default_factory=dict)
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: List[AssertionEvidence] = Field(default_factory=list)

class ExtractedPolicy(BaseModel):
    trigger: str
    rule: str
    priority: float = Field(..., ge=0.0, le=1.0)
    scope: Literal["global", "project", "task"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: List[AssertionEvidence] = Field(default_factory=list)

class ExtractionBundle(BaseModel):
    entities: List[ExtractedEntity] = Field(default_factory=list)
    assertions: List[ExtractedAssertion] = Field(default_factory=list)
    events: List[ExtractedEvent] = Field(default_factory=list)
    policies: List[ExtractedPolicy] = Field(default_factory=list)
