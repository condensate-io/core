import asyncio
import json
import hashlib
import hmac
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from src.db.models import Project, EpisodicItem, Assertion, Policy, Entity, OntologyNode
from src.engine.ner import get_ner_engine
from src.learn.canonicalize import EntityCanonicalizer
from src.engine.edge_synthesizer import EdgeSynthesizer
from src.engine.deterministic import DeterministicCondenser
from src.llm.schemas import ExtractedEntity, ExtractedAssertion, AssertionEvidence
import logging

logger = logging.getLogger(__name__)


from src.engine.thread_shard import get_thread_shard

# Mock LLM client for now (or use real one if env var present)
# In a real implementation this would use the same client as router.py
# For this implementation phase, we focus on the structure and plumbing.

KEY_SECRET = os.getenv("CONDENSATE_SECRET", "super-secret-key").encode()

class Condenser:
    def __init__(self, db: Session):
        self.db = db
        self.ner = get_ner_engine()

    async def distill(self, project_id: uuid.UUID, items: List[EpisodicItem]):
        """
        Main entry point. Takes raw episodic items and "condenses" them 
        into Assertions and Policies.
        """
        if not items:
            return

        # 1. Pipeline components
        print(f"[Condenser] Starting distillation for {len(items)} items. Project: {project_id}")
        canon = EntityCanonicalizer(self.db)
        edge_synth = EdgeSynthesizer(self.db)
        print("[Condenser] Components initialized.")
        
        # 2. Extract Entities from all items (Parallelized)
        # We collect all candidate entities for canonicalization, processing NER on threads
        all_candidate_entities: List[ExtractedEntity] = []
        
        print("[Condenser] Getting thread shard...")
        shard = get_thread_shard()
        print(f"[Condenser] Shard acquired: {shard}")
        ner_futures = []

        
        # 1.5. Fetch Ontology Labels
        ontology_labels = self.db.execute(
            select(OntologyNode.label).where(
                OntologyNode.project_id == project_id,
                OntologyNode.node_type == "entity_type"
            )
        ).scalars().all()
        target_labels = list(set(self.ner.DEFAULT_LABELS + ontology_labels))
        
        for item in items:
            # Offload CPU-bound NER model inference to thread pool
            future = shard.submit(self.ner.extract_entities, item.text, labels=target_labels)
            ner_futures.append(future)
            
        # Collect NER results
        logger.info(f"[Condenser] Waiting for {len(ner_futures)} NER futures (GLiNER check)...")
        from src.engine.stopwords import get_stop_words, MIN_ENTITY_LENGTH
        _sw = get_stop_words()
        for i, future in enumerate(ner_futures):
            try:
                ner_results = future.result()
                print(f"[Condenser] NER future {i} returned {len(ner_results)} entities.")
                for res in ner_results:
                    ent_text = res["text"]
                    # Entity bounding: skip generic / short / stop-word tokens
                    if (len(ent_text) < MIN_ENTITY_LENGTH
                            or ent_text.lower() in _sw):
                        continue
                    all_candidate_entities.append(ExtractedEntity(
                        name=ent_text,
                        type=res["label"].lower() if res["label"] else "concept",
                        aliases=[],
                        confidence=res["score"]
                    ))
            except Exception as e:
                # Log but continue if one fails
                logger.error(f"[Condenser] NER failed for item {i}: {e}")

        # 2. Distillation Strategy
        use_llm = os.getenv("LLM_ENABLED", "false").lower() == "true"
        extracted_facts = []
        
        full_text = "\n".join([item.text for item in items])
        
        if use_llm:
             # LLM Distillation (Slow Path)
             logger.info("[Condenser] Using LLM for distillation.")
             extractor_type = os.getenv("EXTRACTOR_TYPE", "memory_extractor").lower()
             
             if extractor_type == "langextract":
                 from src.agents.langextract import LangExtract
                 extractor = LangExtract()
             else:
                 from src.learn.extractor import MemoryExtractor
                 extractor = MemoryExtractor()

             try:
                 bundles = await extractor.extract(items)
                 for b in bundles:
                     # Convert ExtractedAssertion objects to dicts for our fact loop
                     for ass in b.assertions:
                         fact = {
                             "subject": ass.subject if isinstance(ass.subject, str) else ass.subject.get("name", "unknown"),
                             "predicate": ass.predicate,
                             "object": ass.object if isinstance(ass.object, str) else ass.object.get("name", "unknown"),
                             "confidence": ass.confidence,
                             "type": "fact",
                             "evidence": [ev.model_dump() for ev in ass.evidence]
                         }
                         extracted_facts.append(fact)
                     
                     all_candidate_entities.extend(b.entities)
                     
                 if not extracted_facts:
                     logger.warning("[Condenser] LLM returned zero assertions. Falling back to deterministic.")
                     use_llm = False # Trigger fallback below
             except Exception as e:
                 logger.error(f"[Condenser] LLM extraction failed: {e}. Falling back.")
                 use_llm = False # Trigger fallback
        
        # Fast Path / Fallback (Always runs if LLM disabled or failed)
        if not use_llm:
             logger.info("[Condenser] Using DeterministicCondenser (Fast Path)")
             dc = DeterministicCondenser()
             result = dc.process(full_text, ner_entities=all_candidate_entities)
             logger.info(f"[Condenser] Deterministic process complete. Entities: {len(result.get('entities', []))}")
             
             # Overlap detection
             ner_names = {e.name.lower() for e in all_candidate_entities}
             for det_ent in result.get("entities", []):
                 if not any(det_ent.name.lower() in name for name in ner_names):
                     all_candidate_entities.append(det_ent)
             
             # Add heuristic triplets
             extracted_facts.extend(result.get("facts", []))
             
             if result.get("condensed"):
                 extracted_facts.append({
                     "subject": "Conversation Batch",
                     "predicate": "summarized_as",
                     "object": result["condensed"],
                     "confidence": 1.0,
                     "type": "fact"
                 })

        # 3. Resolve all entities (NER + LLM + Deterministic combined)
        res_map = canon.resolve(str(project_id), all_candidate_entities)

        # 3. Synthesize edges
        entity_ids = [uuid.UUID(eid) for eid in res_map.values()]
        print(f"[Condenser] Synthesizing edges for {len(entity_ids)} entities...")
        
        # Synthesize concept-to-concept edges
        batch_prov = {
            "batch_ts": datetime.utcnow().isoformat(),
            "item_ids": [str(item.id) for item in items]
        }
        edge_count = edge_synth.synthesize(project_id, entity_ids, batch_prov)
        print(f"[Condenser] Synthesized {edge_count} edges.")

        # 3. Create Artifacts with Proof Envelopes (Parallelized)
        source_hashes = [hashlib.sha256(item.text.encode()).hexdigest() for item in items]
        
        # Phase 1: Filter & Prepare (Parallel)
        # We check duplicates synchronously (DB read), then generate envelopes/guardrails in threads
        
        assertion_futures = []
        
        for fact in extracted_facts:
            # Robustly check for type to avoid KeyError: 'type'
            f_type = fact.get("type")
            if f_type == "fact":
                # Check duplication first (must be on main thread with DB session)
                existing = self.db.execute(
                    select(Assertion).where(
                        Assertion.project_id == project_id,
                        Assertion.subject_text == fact.get("subject"),
                        Assertion.predicate == fact.get("predicate"),
                        Assertion.object_text == fact.get("object")
                    )
                ).scalar_one_or_none()
                
                if not existing:
                    # Submit for heavy processing (Guardrails + Crypto + Resolution)
                    future = shard.submit(self._prepare_assertion, project_id, fact, source_hashes, res_map)
                    assertion_futures.append(future)
                    
            elif f_type == "policy":
                # Policies usually vastly fewer, we can just process inline or parallelize similarly
                # For now let's parallelize for consistency
                future = shard.submit(self._prepare_policy, project_id, fact, source_hashes)
                assertion_futures.append(future)
            else:
                logger.warning(f"[Condenser] Fact missing or has unknown type: {fact}")

        # Phase 2: Commit (Sequential Main Thread)
        print(f"[Condenser] Waiting for {len(assertion_futures)} assertion futures...")
        for i, future in enumerate(assertion_futures):
            try:
                result_obj = future.result()
                if result_obj:
                    print(f"[Condenser] Assertion {i} ready. Adding to DB.")
                    self.db.add(result_obj)
            except Exception as e:
                print(f"[Condenser] Failed to prepare assertion/policy {i}: {e}")
        
        print("[Condenser] Committing transaction...")
        self.db.commit()
        print("[Condenser] Distillation complete.")

    def _prepare_assertion(self, project_id: uuid.UUID, fact: dict, source_hashes: List[str], res_map: Optional[Dict[str, str]] = None) -> Optional[Assertion]:
        """
        CPU-bound construction of Assertion: runs Guardrails and Signs Envelope.
        Returns the Assertion object (detached) to be added to session.
        """
        f_pred = fact.get('predicate', 'unknown')
        f_subj = fact.get('subject', 'unknown')
        f_obj = fact.get('object', 'unknown')
        
        # Get IDs from res_map
        subj_id = None
        obj_id = None
        if res_map:
            if f_subj in res_map:
                subj_id = uuid.UUID(res_map[f_subj])
            if f_obj in res_map:
                obj_id = uuid.UUID(res_map[f_obj])

        print(f"[Condenser] _prepare_assertion start: {f_pred}")
        # Run guardrails
        from src.engine.guardrails import GuardrailEngine
        guardrail = GuardrailEngine()
        
        # Check the full assertion text
        subj = fact.get('subject', 'unknown')
        obj = fact.get('object', 'unknown')
        assertion_text = f"{subj} {f_pred} {obj}"
        print(f"[Condenser] Running guardrail check on: {assertion_text}")
        guardrail_result = guardrail.check(assertion_text)
        print(f"[Condenser] Guardrail result: {guardrail_result['should_block']}")
        
        # Determine status based on review mode and guardrail scores
        review_mode = os.getenv("REVIEW_MODE", "manual").lower()
        rejection_reason = None
        
        if review_mode == "auto":
            # Auto-approve unless blocked by guardrails
            if guardrail_result["should_block"]:
                status = "rejected"
                rejection_reason = f"Auto-rejected: {', '.join(guardrail_result['instruction_matches'] + guardrail_result['safety_matches'])}"
            else:
                status = "approved"
        else:
            # Manual review mode
            if guardrail_result["should_block"]:
                status = "rejected"
                rejection_reason = f"Auto-rejected: {', '.join(guardrail_result['instruction_matches'] + guardrail_result['safety_matches'])}"
            else:
                status = "pending_review"

        # Generate Proof Envelope
        envelope = {
            "method": "llm-distillation",
            "model": "gpt-4-mock",
            "inputs": source_hashes,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Sign the envelope
        payload = json.dumps(envelope, sort_keys=True).encode()
        signature = hmac.new(KEY_SECRET, payload, hashlib.sha256).hexdigest()
        envelope["signature"] = signature

        # Provenance: Merge original evidence items with the new envelope
        provenance = fact.get("evidence", []) + [envelope]

        return Assertion(
            project_id=project_id,
            subject_entity_id=subj_id,
            subject_text=f_subj,
            predicate=f_pred,
            object_entity_id=obj_id,
            object_text=f_obj,
            confidence=fact.get("confidence", 0.0),
            status=status,
            rejection_reason=rejection_reason,
            instruction_score=guardrail_result["instruction_score"],
            safety_score=guardrail_result["safety_score"],
            provenance=provenance,
            strength=1.0, # Initial strength
            access_count=0
        )

    def _prepare_policy(self, project_id: uuid.UUID, policy_data: dict, source_hashes: List[str]) -> Policy:
        # Generate Proof Envelope
        envelope = {
            "method": "llm-distillation",
            "model": "gpt-4-mock",
            "inputs": source_hashes,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Sign the envelope
        payload = json.dumps(envelope, sort_keys=True).encode()
        signature = hmac.new(KEY_SECRET, payload, hashlib.sha256).hexdigest()
        envelope["signature"] = signature

        return Policy(
            project_id=project_id,
            trigger=policy_data.get("trigger", "unknown"),
            rule=policy_data.get("rule", "unknown"),
            priority=policy_data.get("priority", 0.7),
            provenance=[envelope]
        )
