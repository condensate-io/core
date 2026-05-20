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

        # Check if condensation is paused
        config_path = "system_config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    if json.load(f).get("condensation_paused", False):
                        logger.info(f"[Condenser] Condensation is paused. Skipping batch for project {project_id}.")
                        return
            except:
                pass

        from src.engine.job_history import log_job
        job_id = f"condense_{project_id}_{int(datetime.utcnow().timestamp())}"
        started_at = datetime.utcnow()
        log_job(job_id, f"Condensation: {project_id}", "running", started_at)

        try:
            # 0. Extract temporal step from metadata
            temporal_step = None
            for item in items:
                step = (item.metadata_ or {}).get("simulation_step")
                if step is not None:
                    if temporal_step is None or step > temporal_step:
                        temporal_step = int(step)

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

            # 2. Distillation Strategy (Hybrid: Deterministic Baseline + LLM Enrichment)
            full_text = "\n".join([item.text for item in items])
            extracted_facts = []
            
            # --- Phase 1: Deterministic L3 (Fast Path) ---
            logger.info("[Condenser] Running Deterministic L3 extraction...")
            dc = DeterministicCondenser()
            det_result = dc.process(full_text, ner_entities=all_candidate_entities, ontology_nodes=ontology_labels)
            
            # Seed our fact list with L3 findings
            extracted_facts.extend(det_result.get("facts", []))
            # Merge deterministic entities back into the candidate pool for canonicalization
            all_candidate_entities.extend(det_result.get("entities", []))
            if det_result.get("condensed"):
                extracted_facts.append({
                    "subject": "Conversation Batch",
                    "predicate": "summarized_as",
                    "object": det_result["condensed"],
                    "confidence": 0.7, # L3 baseline
                    "type": "fact"
                })
            
            # --- Phase 2: LLM Enrichment L2 (Smarter Path) ---
            if os.getenv("LLM_ENABLED", "false").lower() == "true":
                 logger.info("[Condenser] Running LLM L2 enrichment...")
                 from src.learn.extractor import MemoryExtractor
                 extractor = MemoryExtractor()
                 
                 try:
                     bundles = await extractor.extract(items)
                     for b in bundles:
                         # Merge entities from LLM
                         all_candidate_entities.extend(b.entities)
                         
                         # Add facts from LLM
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
                 except Exception as e:
                     logger.error(f"[Condenser] LLM enrichment failed: {e}. Progressing with L3 results only.")

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
            edge_count = edge_synth.synthesize(project_id, entity_ids, batch_prov, temporal_step=temporal_step)
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
                    ).scalars().first()
                    
                    if not existing:
                        # Submit for heavy processing (Guardrails + Crypto + Resolution)
                        future = shard.submit(self._prepare_assertion, project_id, fact, source_hashes, res_map, temporal_step)
                        assertion_futures.append(future)
                        
                elif f_type == "policy":
                    # Policies usually vastly fewer, we can just process inline or parallelize similarly
                    # For now let's parallelize for consistency
                    future = shard.submit(self._prepare_policy, project_id, fact, source_hashes, temporal_step)
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

            # --- Synapse Engine Integration ---
            try:
                from src.synapses.config import synapse_config
                if synapse_config.ENABLED:
                    from src.synapses.engine import SynapseEngine
                    synapse_engine = SynapseEngine(self.db)
                    # Collect IDs of newly created assertions
                    new_assertion_ids = [res.id for res in [f.result() for f in assertion_futures] if res and isinstance(res, Assertion)]
                    if new_assertion_ids:
                        logger.info(f"[Condenser] Emitting synapses for {len(new_assertion_ids)} assertions...")
                        # Pass IDs and temporal step for relationship analysis
                        synapse_engine.create_synapses_from_condensation(project_id, new_assertion_ids, temporal_step=temporal_step)
                        
                        # 2. Trigger consolidation cycle (Synthesize higher-order memories)
                        from src.synapses.consolidation import MemoryConsolidator
                        consolidator = MemoryConsolidator(self.db)
                        await consolidator.run_consolidation_cycle(project_id)
            except Exception as se_exc:
                logger.error(f"[Condenser] Synapse Engine failed: {se_exc}")
            
            finished_at = datetime.utcnow()
            duration = int((finished_at - started_at).total_seconds() * 1000)
            log_job(job_id, f"Condensation: {project_id}", "success", started_at, finished_at, duration)
        except Exception as e:
            logger.error(f"[Condenser] Distillation failed: {e}")
            log_job(job_id, f"Condensation: {project_id}", "error", started_at, datetime.utcnow(), error=str(e))
            self.db.rollback()
            raise e
        
        print("[Condenser] Distillation complete.")

    def _prepare_assertion(self, project_id: uuid.UUID, fact: dict, source_hashes: List[str], res_map: Optional[Dict[str, str]] = None, temporal_step: Optional[int] = None) -> Optional[Assertion]:
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
        config_path = "system_config.json"
        review_mode = os.getenv("REVIEW_MODE", "manual").lower()
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    review_mode = json.load(f).get("review_mode", review_mode)
            except:
                pass
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
            access_count=0,
            temporal_step=temporal_step
        )

    def _prepare_policy(self, project_id: uuid.UUID, policy_data: dict, source_hashes: List[str], temporal_step: Optional[int] = None) -> Policy:
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
