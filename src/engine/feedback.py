"""Answer-aware memory reinforcement driven by eval feedback."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from src.db.models import Assertion
from src.engine.cognitive import CognitiveService
from src.synapses.config import synapse_config
from src.synapses.engine import SynapseEngine

logger = logging.getLogger(__name__)


class MemoryFeedbackService:
    """Reinforce retrieval paths that produced correct answers; decay misleading ones."""

    def __init__(self, db: Session):
        self.db = db
        self.cognitive = CognitiveService(db)

    def apply_feedback(
        self,
        source_ids: List[uuid.UUID],
        *,
        correct: bool,
        gold_evidence_ids: Optional[List[str]] = None,
        retrieval_path: Optional[List[str]] = None,
    ) -> dict:
        if not source_ids:
            return {"strengthened": 0, "decayed": 0}

        if correct:
            self.cognitive.hebbian_update(source_ids)
            strengthened = len(source_ids)
            if synapse_config.ENABLED:
                try:
                    syn_engine = SynapseEngine(self.db)
                    syn_engine.strengthen_on_retrieval(source_ids, query="feedback:correct")
                except Exception as exc:
                    logger.warning("Synapse feedback strengthen failed: %s", exc)
            if gold_evidence_ids:
                self._boost_evidence_aligned_assertions(source_ids, gold_evidence_ids)
            return {"strengthened": strengthened, "decayed": 0, "path": retrieval_path or []}

        decayed = self._decay_misleading(source_ids)
        return {"strengthened": 0, "decayed": decayed, "path": retrieval_path or []}

    def _boost_evidence_aligned_assertions(
        self,
        source_ids: List[uuid.UUID],
        gold_evidence_ids: List[str],
    ) -> None:
        gold_set = {g.upper() for g in gold_evidence_ids}
        assertions = self.db.query(Assertion).filter(Assertion.id.in_(source_ids)).all()
        now = datetime.utcnow()
        for assertion in assertions:
            prov = assertion.provenance or []
            dia_ids = {
                str(p.get("dia_id", "")).upper()
                for p in prov
                if isinstance(p, dict) and p.get("dia_id")
            }
            quote_blob = " ".join(
                str(p.get("quote", "")) for p in prov if isinstance(p, dict)
            ).upper()
            if dia_ids & gold_set or any(g in quote_blob for g in gold_set):
                assertion.strength = min(assertion.strength + 0.15, 5.0)
                assertion.access_count += 1
                assertion.last_accessed_at = now
                self.db.add(assertion)
        self.db.commit()

    def _decay_misleading(self, source_ids: List[uuid.UUID]) -> int:
        now = datetime.utcnow()
        updated = (
            self.db.query(Assertion)
            .filter(Assertion.id.in_(source_ids))
            .update(
                {
                    Assertion.strength: Assertion.strength * 0.95,
                    Assertion.last_accessed_at: now,
                },
                synchronize_session=False,
            )
        )
        self.db.commit()
        return int(updated or 0)
