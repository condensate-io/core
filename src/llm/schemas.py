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
    type: Literal["person", "org", "system", "project", "tool", "concept", "artifact", "resource", "event", "other"]
    aliases: List[str] = Field(default_factory=list, description="Known aliases for this entity")
    confidence: float = Field(0.8, ge=0.0, le=1.0)

    @model_validator(mode="before")
    @classmethod
    def robust_parsing(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # 1. Recovery for missing 'name' if 'references' or 'value' exists
            if not data.get("name"):
                if data.get("references"):
                    data["name"] = str(data.get("references", [""])[0])
                elif data.get("aliases"):
                    data["name"] = str(data.get("aliases", [""])[0])
                elif data.get("value"):
                    data["name"] = str(data.get("value"))
            
            # 2. Recovery for missing 'type' if 'label' or 'category' or 'kind' exists
            if not data.get("type"):
                if data.get("label"):
                    data["type"] = data.get("label")
                elif data.get("category"):
                    data["type"] = data.get("category")
                elif data.get("kind"):
                    data["type"] = data.get("kind")
            
            # 3. Map unknown types to 'other' (Fixes Literal errors)
            valid_types = {"person", "org", "system", "project", "tool", "concept", "artifact", "resource", "event", "other"}
            current_type = str(data.get("type", "other")).lower()
            if current_type not in valid_types:
                # Common mapping fallbacks
                if "location" in current_type or "place" in current_type:
                    data["type"] = "other"
                elif "document" in current_type:
                    data["type"] = "artifact"
                else:
                    data["type"] = "other"
            else:
                data["type"] = current_type
                    
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
    confidence: float = Field(0.8, ge=0.0, le=1.0)
    evidence: List[AssertionEvidence] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def robust_parsing(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Default confidence if LLM omits it
            if "confidence" not in data or data["confidence"] is None:
                data["confidence"] = 0.8
            # Ensure polarity is an int
            if "polarity" in data and data["polarity"] is not None:
                try:
                    data["polarity"] = int(data["polarity"])
                except:
                    data["polarity"] = 1
            else:
                data["polarity"] = 1
        return data

class ExtractedEvent(BaseModel):
    type: str # meeting, decision, etc
    summary: str
    occurred_at: Optional[str] = None # ISO8601
    participants: List[Any] = Field(default_factory=list) # Entity references
    attributes: dict = Field(default_factory=dict)
    confidence: float = Field(0.8, ge=0.0, le=1.0)
    evidence: List[AssertionEvidence] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def robust_parsing(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "confidence" not in data or data["confidence"] is None:
                data["confidence"] = 0.8
        return data

class ExtractedPolicy(BaseModel):
    trigger: str = Field("always", description="Condition that activates this policy")
    rule: str = Field(..., description="The behavioral rule/constraint")
    priority: float = Field(0.7, ge=0.0, le=1.0)
    scope: Literal["global", "project", "task"] = Field("global")
    confidence: float = Field(0.8, ge=0.0, le=1.0)
    evidence: List[AssertionEvidence] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def robust_parsing(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # 1. Trigger recovery (Fixes: Input should be a valid string [type=dict])
            trigger = data.get("trigger")
            if isinstance(trigger, dict):
                 # Try to extract the most descriptive string from the dict
                 data["trigger"] = str(trigger.get("type") or trigger.get("name") or trigger.get("summary") or "general_trigger")
            elif not trigger:
                data["trigger"] = "always"
            else:
                data["trigger"] = str(trigger)
            
            # 2. Rule recovery
            if not data.get("rule"):
                data["rule"] = "undetermined rule"

            # 3. Priority recovery (Fixes: Input should be less than or equal to 1)
            priority = data.get("priority")
            if priority is None:
                 data["priority"] = 0.7
            else:
                try:
                    p_val = float(priority)
                    if p_val < 0:
                        data["priority"] = 0.0
                    elif p_val > 1:
                        # If the LLM output 10 (on 1-10 scale), normalize it to 1.0
                        if p_val > 1.0 and p_val <= 10.0:
                             data["priority"] = p_val / 10.0
                        else:
                             data["priority"] = 1.0
                    else:
                        data["priority"] = p_val
                except (ValueError, TypeError):
                    data["priority"] = 0.7
            
            # 4. Scope recovery (Fixes: Input should be 'global', 'project' or 'task' [type=dict])
            valid_scopes = {"global", "project", "task"}
            scope = data.get("scope")
            if isinstance(scope, dict):
                 # Try to see if there is a 'type' or 'scope' inside the dict
                 scope_val = str(scope.get("type") or scope.get("scope") or "global").lower()
                 if scope_val in valid_scopes:
                      data["scope"] = scope_val
                 else:
                      data["scope"] = "global"
            elif isinstance(scope, list):
                data["scope"] = "global"
            elif isinstance(scope, str):
                scope_low = scope.lower()
                if scope_low not in valid_scopes:
                    data["scope"] = "global"
                else:
                    data["scope"] = scope_low
            else:
                data["scope"] = "global"

            # 5. Confidence default
            if "confidence" not in data or data["confidence"] is None:
                data["confidence"] = 0.8
            
        return data

class ExtractionBundle(BaseModel):
    entities: List[ExtractedEntity] = Field(default_factory=list)
    assertions: List[ExtractedAssertion] = Field(default_factory=list)
    events: List[ExtractedEvent] = Field(default_factory=list)
    policies: List[ExtractedPolicy] = Field(default_factory=list)
