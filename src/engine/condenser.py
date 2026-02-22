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

from src.db.models import Project, EpisodicItem, Assertion, Policy, Entity
from src.engine.ner import get_ner_engine
from src.learn.canonicalize import EntityCanonicalizer
from src.engine.edge_synthesizer import EdgeSynthesizer
from src.llm.schemas import ExtractedEntity, ExtractedAssertion, AssertionEvidence


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

        
        for item in items:
            # Offload CPU-bound NER model inference to thread pool
            future = shard.submit(self.ner.extract_entities, item.text)
            ner_futures.append(future)
            
        # Collect NER results
        print(f"[Condenser] Waiting for {len(ner_futures)} NER futures...")
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
                print(f"[Condenser] NER failed for item {i}: {e}")

        # 2. Distillation Strategy
        # Check if LLM is enabled (default False for "No-LLM by default")
        use_llm = os.getenv("LLM_ENABLED", "false").lower() == "true"
        
        extracted_facts = []
        
        if use_llm:
             # LLM Distillation (Slow Path)
             extractor_type = os.getenv("EXTRACTOR_TYPE", "memory_extractor").lower()
             
             if extractor_type == "langextract":
                 print("[Condenser] Using LangExtract for distillation.")
                 from src.agents.langextract import LangExtract
                 extractor = LangExtract()
             else:
                 print("[Condenser] Using MemoryExtractor for distillation.")
                 from src.learn.extractor import MemoryExtractor
                 extractor = MemoryExtractor()

             from src.learn.consolidate import KnowledgeConsolidator
             
             bundles = await extractor.extract(items)
             
             # 1. Gather all entities and assertions across bundles
             llm_entities = []
             llm_assertions = []
             for b in bundles:
                 llm_entities.extend(b.entities)
                 llm_assertions.extend(b.assertions)
             
             all_candidate_entities.extend(llm_entities)
             
             # 2. Canonicalize FIRST (so we have IDs for assertions)
             res_map = canon.resolve(str(project_id), all_candidate_entities)
             
             # 3. Consolidate Assertions
             consolidator = KnowledgeConsolidator(self.db)
             # LLM assertions should also follow REVIEW_MODE (handled inside consolidate)
             consolidator.consolidate(str(project_id), llm_assertions, res_map)
             
             # Also run deterministic for a quick summary even if LLM is on
             from src.engine.deterministic import DeterministicCondenser
             dc = DeterministicCondenser()
             full_text = "\n".join([item.text for item in items])
             result = dc.process(full_text)
             if result.get("condensed"):
                 extracted_facts.append({
                     "subject": "Conversation Batch",
                     "predicate": "summarized_as",
                     "object": result["condensed"],
                     "confidence": 1.0,
                     "type": "fact"
                 })
        else:
             # Deterministic L3-Condensation (Fast Path)
             print("[Condenser] Using DeterministicCondenser (Fast Path)")
             from src.engine.deterministic import DeterministicCondenser
             dc = DeterministicCondenser()
             
             # Combine text for processing or process individually
             # Let's process the combined text of the batch for broader context
             full_text = "\n".join([item.text for item in items])
             print(f"[Condenser] Processing text length: {len(full_text)}")
             result = dc.process(full_text)
             print(f"[Condenser] Deterministic process complete. Entities: {len(result.get('entities', []))}")
             
             # Combine results
             all_candidate_entities.extend(result.get("entities", []))
             
             # 2. Condensed Summary (Stored as a high-level assertion)
             if result.get("condensed"):
                 extracted_facts.append({
                     "subject": "Conversation Batch",
                     "predicate": "summarized_as",
                     "object": result["condensed"],
                     "confidence": 1.0,
                     "type": "fact"
                 })
             
             # Resolve all entities (NER + deterministic)
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
            if fact["type"] == "fact":
                # Check duplication first (must be on main thread with DB session)
                existing = self.db.execute(
                    select(Assertion).where(
                        Assertion.project_id == project_id,
                        Assertion.subject_text == fact["subject"],
                        Assertion.predicate == fact["predicate"],
                        Assertion.object_text == fact["object"]
                    )
                ).scalar_one_or_none()
                
                if not existing:
                    # Submit for heavy processing (Guardrails + Crypto)
                    future = shard.submit(self._prepare_assertion, project_id, fact, source_hashes)
                    assertion_futures.append(future)
                    
            elif fact["type"] == "policy":
                # Policies usually vastly fewer, we can just process inline or parallelize similarly
                # For now let's parallelize for consistency
                future = shard.submit(self._prepare_policy, project_id, fact, source_hashes)
                assertion_futures.append(future)

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

    def _prepare_assertion(self, project_id: uuid.UUID, fact: dict, source_hashes: List[str]) -> Optional[Assertion]:
        """
        CPU-bound construction of Assertion: runs Guardrails and Signs Envelope.
        Returns the Assertion object (detached) to be added to session.
        """
        print(f"[Condenser] _prepare_assertion start: {fact['predicate']}")
        # Run guardrails
        from src.engine.guardrails import GuardrailEngine
        guardrail = GuardrailEngine()
        
        # Check the full assertion text
        assertion_text = f"{fact['subject']} {fact['predicate']} {fact['object']}"
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

        return Assertion(
            project_id=project_id,
            subject_text=fact["subject"],
            predicate=fact["predicate"],
            object_text=fact["object"],
            confidence=fact["confidence"],
            status=status,
            rejection_reason=rejection_reason,
            instruction_score=guardrail_result["instruction_score"],
            safety_score=guardrail_result["safety_score"],
            provenance=[envelope],
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
            trigger=policy_data["trigger"],
            rule=policy_data["rule"],
            priority=policy_data["priority"],
            provenance=[envelope]
        )
