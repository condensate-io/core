import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.db.models import Relation

class EdgeSynthesizer:
    def __init__(self, db: Session):
        self.db = db

    def synthesize(self, project_id: uuid.UUID, entity_ids: List[uuid.UUID], batch_provenance: dict, temporal_step: Optional[int] = None) -> int:
        """
        For each pair of entities in the batch, upsert a co-occurrence Relation edge.
        Returns count of edges created/updated.
        """
        if len(entity_ids) < 2:
            return 0

        edges_processed = 0
        now = datetime.utcnow()

        # Create unique pairs (A, B) where A < B to avoid duplicate undirected edges if preferred,
        # but here we follow the existing Relation model which seems to be directed (from_id, to_id).
        # We will create bidirectional links for co-occurrence to ensure symmetry in the graph.
        
        for i, id_a in enumerate(entity_ids):
            for id_b in entity_ids[i+1:]:
                # Bidirectional: A -> B and B -> A
                edges_processed += self._upsert_relation(project_id, id_a, id_b, batch_provenance, now, temporal_step)
                edges_processed += self._upsert_relation(project_id, id_b, id_a, batch_provenance, now, temporal_step)

        return edges_processed

    def _upsert_relation(self, project_id: uuid.UUID, from_id: uuid.UUID, to_id: uuid.UUID, 
                         batch_provenance: dict, timestamp: datetime, temporal_step: Optional[int] = None) -> int:
        """
        Internal helper to upsert a directed relationship between two entities.
        """
        # Exact match check
        stmt = select(Relation).where(
            Relation.project_id == project_id,
            Relation.from_id == from_id,
            Relation.to_id == to_id,
            Relation.relation_type == "co_occurs_with"
        )
        existing = self.db.execute(stmt).scalars().first()

        if existing:
            # Reinforce (Hebbian-like growth)
            existing.strength = min(existing.strength + 0.1, 5.0)
            existing.access_count += 1
            existing.last_accessed_at = timestamp
            
            if temporal_step is not None:
                if existing.temporal_start is None or temporal_step < existing.temporal_start:
                    existing.temporal_start = temporal_step
                if existing.temporal_end is None or temporal_step > existing.temporal_end:
                    existing.temporal_end = temporal_step
            
            # Update provenance (limit size to avoid JSONB bloat)
            prov = existing.provenance or []
            # Only add if batch not already in prov
            if not any(p.get("batch_ts") == batch_provenance.get("batch_ts") for p in prov):
                prov.append(batch_provenance)
                # Keep last 10 evidence points
                existing.provenance = prov[-10:]
            
            self.db.add(existing)
        else:
            # Create new
            new_rel = Relation(
                id=uuid.uuid4(),
                project_id=project_id,
                from_id=from_id,
                from_kind="entity",
                relation_type="co_occurs_with",
                to_id=to_id,
                to_kind="entity",
                strength=1.0, # Initial strength
                confidence=1.0,
                provenance=[batch_provenance],
                access_count=1,
                last_accessed_at=timestamp,
                temporal_start=temporal_step,
                temporal_end=temporal_step
            )
            self.db.add(new_rel)
        
        return 1
