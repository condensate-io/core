import hashlib
import hmac
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from src.config import settings
from src.config_cache import load_json_config
from src.db.models import Assertion, EpisodicItem, OntologyNode, Policy
from src.engine.deterministic import DeterministicCondenser
from src.engine.edge_synthesizer import EdgeSynthesizer
from src.engine.ner import get_ner_engine
from src.engine.thread_shard import get_thread_shard
from src.learn.canonicalize import EntityCanonicalizer
from src.llm.schemas import ExtractedEntity

logger = logging.getLogger(__name__)


def build_proof_envelope(
    payload: Dict[str, Any],
    input_hashes: List[str],
    *,
    method: str = "llm-distillation",
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Build an RFC-0002 proof envelope with HMAC signature over payload + provenance."""
    provenance = {
        "method": method,
        "model": model or settings.LLM_MODEL,
        "input_hashes": input_hashes,
    }
    unsigned = {"payload": payload, "provenance": provenance}
    sign_bytes = json.dumps(unsigned, sort_keys=True).encode()
    signature = hmac.new(
        settings.CONDENSATE_SECRET.encode(),
        sign_bytes,
        hashlib.sha256,
    ).hexdigest()
    return {**unsigned, "signature": signature}


def verify_proof_envelope(envelope: Dict[str, Any]) -> bool:
    """Verify an RFC-0002 proof envelope HMAC signature."""
    try:
        unsigned = {"payload": envelope["payload"], "provenance": envelope["provenance"]}
        expected_sig = envelope["signature"]
    except KeyError:
        return False
    sign_bytes = json.dumps(unsigned, sort_keys=True).encode()
    computed = hmac.new(
        settings.CONDENSATE_SECRET.encode(),
        sign_bytes,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(computed, expected_sig)


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
        system_config = load_json_config("system_config.json", settings.CONFIG_CACHE_TTL_SECONDS)
        if system_config.get("condensation_paused", False):
            logger.info(f"[Condenser] Condensation is paused. Skipping batch for project {project_id}.")
            return

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
            logger.info("Starting distillation for %s items. Project: %s", len(items), project_id)
            canon = EntityCanonicalizer(self.db)
            edge_synth = EdgeSynthesizer(self.db)
            logger.debug("Components initialized.")

            # 2. Extract Entities from all items (Parallelized)
            # We collect all candidate entities for canonicalization, processing NER on threads
            all_candidate_entities: List[ExtractedEntity] = []

            logger.debug("Getting thread shard...")
            shard = get_thread_shard()
            logger.debug("Shard acquired: %s", shard)
            ner_futures = []

            # 1.5. Fetch Ontology Labels
            ontology_labels = (
                self.db.execute(
                    select(OntologyNode.label).where(
                        OntologyNode.project_id == project_id, OntologyNode.node_type == "entity_type"
                    )
                )
                .scalars()
                .all()
            )
            target_labels = list(set(self.ner.DEFAULT_LABELS + ontology_labels))

            for item in items:
                # Offload CPU-bound NER model inference to thread pool
                future = shard.submit(self.ner.extract_entities, item.text, labels=target_labels)
                ner_futures.append(future)

            # Collect NER results
            logger.info(f"[Condenser] Waiting for {len(ner_futures)} NER futures (GLiNER check)...")
            from src.engine.stopwords import MIN_ENTITY_LENGTH, get_stop_words

            _sw = get_stop_words()
            for i, future in enumerate(ner_futures):
                try:
                    ner_results = future.result()
                    logger.debug("NER future %s returned %s entities.", i, len(ner_results))
                    for res in ner_results:
                        ent_text = res["text"]
                        # Entity bounding: skip generic / short / stop-word tokens
                        if len(ent_text) < MIN_ENTITY_LENGTH or ent_text.lower() in _sw:
                            continue
                        all_candidate_entities.append(
                            ExtractedEntity(
                                name=ent_text,
                                type=res["label"].lower() if res["label"] else "concept",
                                aliases=[],
                                confidence=res["score"],
                            )
                        )
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
                extracted_facts.append(
                    {
                        "subject": "Conversation Batch",
                        "predicate": "summarized_as",
                        "object": det_result["condensed"],
                        "confidence": 0.7,  # L3 baseline
                        "type": "fact",
                    }
                )

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
                                "subject": ass.subject
                                if isinstance(ass.subject, str)
                                else ass.subject.get("name", "unknown"),
                                "predicate": ass.predicate,
                                "object": ass.object
                                if isinstance(ass.object, str)
                                else ass.object.get("name", "unknown"),
                                "confidence": ass.confidence,
                                "type": "fact",
                                "evidence": [ev.model_dump() for ev in ass.evidence],
                            }
                            extracted_facts.append(fact)
                except Exception as e:
                    logger.error(f"[Condenser] LLM enrichment failed: {e}. Progressing with L3 results only.")

            # 3. Resolve all entities (NER + LLM + Deterministic combined)
            res_map = canon.resolve(str(project_id), all_candidate_entities)

            # 3. Synthesize edges
            entity_ids = [uuid.UUID(eid) for eid in res_map.values()]
            logger.info("Synthesizing edges for %s entities...", len(entity_ids))

            # Synthesize concept-to-concept edges
            batch_prov = {"batch_ts": datetime.utcnow().isoformat(), "item_ids": [str(item.id) for item in items]}
            edge_count = edge_synth.synthesize(project_id, entity_ids, batch_prov, temporal_step=temporal_step)
            logger.info("Synthesized %s edges.", edge_count)

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
                    existing = (
                        self.db.execute(
                            select(Assertion).where(
                                Assertion.project_id == project_id,
                                Assertion.subject_text == fact.get("subject"),
                                Assertion.predicate == fact.get("predicate"),
                                Assertion.object_text == fact.get("object"),
                            )
                        )
                        .scalars()
                        .first()
                    )

                    if not existing:
                        # Submit for heavy processing (Guardrails + Crypto + Resolution)
                        future = shard.submit(
                            self._prepare_assertion, project_id, fact, source_hashes, res_map, temporal_step
                        )
                        assertion_futures.append(future)

                elif f_type == "policy":
                    # Policies usually vastly fewer, we can just process inline or parallelize similarly
                    # For now let's parallelize for consistency
                    future = shard.submit(self._prepare_policy, project_id, fact, source_hashes, temporal_step)
                    assertion_futures.append(future)
                else:
                    logger.warning(f"[Condenser] Fact missing or has unknown type: {fact}")

            # Phase 2: Commit (Sequential Main Thread)
            logger.debug("Waiting for %s assertion futures...", len(assertion_futures))
            for i, future in enumerate(assertion_futures):
                try:
                    result_obj = future.result()
                    if result_obj:
                        logger.debug("Assertion %s ready. Adding to DB.", i)
                        self.db.add(result_obj)
                except Exception as e:
                    logger.warning("Failed to prepare assertion/policy %s: %s", i, e)

            logger.debug("Committing transaction...")
            self.db.commit()

            # --- Synapse Engine Integration ---
            try:
                from src.synapses.config import synapse_config

                if synapse_config.ENABLED:
                    from src.synapses.engine import SynapseEngine

                    synapse_engine = SynapseEngine(self.db)
                    # Collect IDs of newly created assertions
                    new_assertion_ids = [
                        res.id for res in [f.result() for f in assertion_futures] if res and isinstance(res, Assertion)
                    ]
                    if new_assertion_ids:
                        logger.info(f"[Condenser] Emitting synapses for {len(new_assertion_ids)} assertions...")
                        # Pass IDs and temporal step for relationship analysis
                        synapse_engine.create_synapses_from_condensation(
                            project_id, new_assertion_ids, temporal_step=temporal_step
                        )

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

        logger.info("Distillation complete.")

    def _prepare_assertion(
        self,
        project_id: uuid.UUID,
        fact: dict,
        source_hashes: List[str],
        res_map: Optional[Dict[str, str]] = None,
        temporal_step: Optional[int] = None,
    ) -> Optional[Assertion]:
        """
        CPU-bound construction of Assertion: runs Guardrails and Signs Envelope.
        Returns the Assertion object (detached) to be added to session.
        """
        f_pred = fact.get("predicate", "unknown")
        f_subj = fact.get("subject", "unknown")
        f_obj = fact.get("object", "unknown")

        # Get IDs from res_map
        subj_id = None
        obj_id = None
        if res_map:
            if f_subj in res_map:
                subj_id = uuid.UUID(res_map[f_subj])
            if f_obj in res_map:
                obj_id = uuid.UUID(res_map[f_obj])

        logger.debug("_prepare_assertion start: %s", f_pred)
        # Run guardrails
        from src.engine.guardrails import GuardrailEngine

        guardrail = GuardrailEngine()

        # Check the full assertion text
        subj = fact.get("subject", "unknown")
        obj = fact.get("object", "unknown")
        assertion_text = f"{subj} {f_pred} {obj}"
        logger.debug("Running guardrail check on: %s", assertion_text)
        guardrail_result = guardrail.check(assertion_text)
        logger.debug("Guardrail result: should_block=%s", guardrail_result["should_block"])

        # Determine status based on review mode and guardrail scores
        system_config = load_json_config("system_config.json", settings.CONFIG_CACHE_TTL_SECONDS)
        review_mode = system_config.get("review_mode", os.getenv("REVIEW_MODE", "manual").lower())
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

        assertion_id = uuid.uuid4()
        envelope = build_proof_envelope(
            {
                "assertion_id": str(assertion_id),
                "subject_text": f_subj,
                "predicate": f_pred,
                "object_text": f_obj,
                "distilled_at": datetime.utcnow().isoformat() + "Z",
            },
            source_hashes,
        )

        # Provenance: Merge original evidence items with the new envelope
        provenance = fact.get("evidence", []) + [envelope]

        return Assertion(
            id=assertion_id,
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
            strength=1.0,  # Initial strength
            access_count=0,
            temporal_step=temporal_step,
        )

    def _prepare_policy(
        self, project_id: uuid.UUID, policy_data: dict, source_hashes: List[str], temporal_step: Optional[int] = None
    ) -> Policy:
        policy_id = uuid.uuid4()
        envelope = build_proof_envelope(
            {
                "policy_id": str(policy_id),
                "trigger": policy_data.get("trigger", "unknown"),
                "rule": policy_data.get("rule", "unknown"),
                "distilled_at": datetime.utcnow().isoformat() + "Z",
            },
            source_hashes,
        )

        return Policy(
            id=policy_id,
            project_id=project_id,
            trigger=policy_data.get("trigger", "unknown"),
            rule=policy_data.get("rule", "unknown"),
            priority=policy_data.get("priority", 0.7),
            provenance=[envelope],
        )
