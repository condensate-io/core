from typing import List, Optional, Any, Literal
from pydantic import BaseModel, Field, UUID4, field_validator
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
    confidence: float = Field(..., ge=0.0, le=1.0)

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
