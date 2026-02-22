from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import select
from src.db.models import Assertion, Entity
from src.llm.schemas import ExtractedAssertion
import uuid
import os
from src.engine.guardrails import GuardrailEngine

class KnowledgeConsolidator:
    def __init__(self, db: Session):
        self.db = db
        self.guardrail = GuardrailEngine()

    def consolidate(self, project_id: str, assertions: List[ExtractedAssertion], entity_map: Dict[str, str], status: str = None):
        """
        Upserts assertions into the Knowledge Graph.
        Links Subjects/Objects to Entity IDs using entity_map.
        """
        for claim in assertions:
            # 1. Resolve Subject
            subj_id, subj_text = self._resolve_ref(claim.subject, entity_map)
            # 2. Resolve Object
            obj_id, obj_text = self._resolve_ref(claim.object, entity_map)

            # 3. Guardrail Check
            assertion_text = f"{subj_text} {claim.predicate} {obj_text}"
            guard_res = self.guardrail.check(assertion_text)
            
            # Determine status
            final_status = status
            rejection_reason = None
            
            if status is None:
                review_mode = os.getenv("REVIEW_MODE", "manual").lower()
                if guard_res["should_block"]:
                    final_status = "rejected"
                    rejection_reason = f"Auto-rejected by Guardrails: {', '.join(guard_res['instruction_matches'] + guard_res['safety_matches'])}"
                elif review_mode == "manual":
                    final_status = "pending_review"
                else:
                    final_status = "active"

            # 4. Check for duplicates (Subject + Predicate + Object + Polarity)
            stmt = select(Assertion).where(
                Assertion.project_id == project_id,
                Assertion.subject_entity_id == subj_id,
                Assertion.subject_text == subj_text,
                Assertion.predicate == claim.predicate.lower(),
                Assertion.object_entity_id == obj_id,
                Assertion.object_text == obj_text,
                Assertion.polarity == claim.polarity
            )
            existing = self.db.execute(stmt).scalars().first()

            if existing:
                # Update provenance and confidence
                if claim.evidence:
                    current_prov = existing.provenance or []
                    existing_ev_ids = {e.get("episodic_id") for e in current_prov}
                    
                    for ev in claim.evidence:
                        if str(ev.episodic_id) not in existing_ev_ids:
                            current_prov.append(ev.model_dump())
                    
                    existing.provenance = current_prov
                    
                # Update confidence and guardrail scores
                existing.confidence = max(existing.confidence, claim.confidence)
                existing.instruction_score = max(existing.instruction_score, guard_res["instruction_score"])
                existing.safety_score = max(existing.safety_score, guard_res["safety_score"])
                self.db.add(existing)

            else:
                new_assertion = Assertion(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    subject_entity_id=subj_id,
                    subject_text=subj_text,
                    predicate=claim.predicate.lower(),
                    object_entity_id=obj_id,
                    object_text=obj_text,
                    polarity=claim.polarity,
                    confidence=claim.confidence,
                    status=final_status,
                    rejection_reason=rejection_reason,
                    instruction_score=guard_res["instruction_score"],
                    safety_score=guard_res["safety_score"],
                    provenance=[e.model_dump() for e in claim.evidence]
                )
                self.db.add(new_assertion)
        
        self.db.commit()

    def _resolve_ref(self, ref: any, entity_map: Dict[str, str]):
        """
        Helper to parse the extracted subject/object (which can be a dict or string)
        and map it to a UUID if possible.
        """
        # If ref is a dict from LLM schema: {'type': 'entity', 'name': 'Bob'}
        if isinstance(ref, dict):
            if ref.get("type") == "entity":
                name = ref.get("name")
                if name in entity_map:
                    return uuid.UUID(entity_map[name]), name
                return None, name # Fallback to text
            elif ref.get("type") == "literal":
                return None, ref.get("value")
        
        # If ref is just a string
        if isinstance(ref, str):
             if ref in entity_map:
                 return uuid.UUID(entity_map[ref]), ref
             return None, ref

        return None, str(ref)
