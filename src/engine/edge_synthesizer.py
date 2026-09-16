import logging
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.db.models import Relation

logger = logging.getLogger(__name__)

# Hard cap on the number of entities considered per batch for pairwise
# co-occurrence synthesis. Pair count grows O(n^2), so this bounds worst-case
# DB and CPU work for very large ingestion batches (e.g. a big codebase dump).
DEFAULT_MAX_ENTITIES = 40


class EdgeSynthesizer:
    def __init__(self, db: Session):
        self.db = db

    def synthesize(self, project_id: uuid.UUID, entity_ids: List[uuid.UUID], batch_provenance: dict, temporal_step: Optional[int] = None) -> int:
        """
        For each pair of entities in the batch, upsert a co-occurrence Relation edge.

        This performs a single batched SELECT for all relevant existing relations
        (instead of one SELECT + one write per pair/direction) and bulk-upserts
        any missing edges, so the DB round-trip count is O(1) per batch rather
        than O(n^2), without racing into duplicate rows under concurrent runs.

        Returns count of edges created/updated.
        """
        if len(entity_ids) < 2:
            return 0

        max_entities = max(
            2, int(os.getenv("EDGE_SYNTH_MAX_ENTITIES", str(DEFAULT_MAX_ENTITIES)))
        )
        # Unique ids only, preserving order/determinism for pair generation.
        unique_ids = list(dict.fromkeys(entity_ids))
        if len(unique_ids) > max_entities:
            logger.warning(
                "[EdgeSynthesizer] Batch has %s entities; capping to %s to bound "
                "O(n^2) co-occurrence synthesis.",
                len(unique_ids),
                max_entities,
            )
            unique_ids = unique_ids[:max_entities]

        if len(unique_ids) < 2:
            return 0

        now = datetime.utcnow()

        # 1. Single batched fetch of every existing co-occurrence relation
        #    among the candidate entities (both directions at once).
        existing_map: Dict[Tuple[uuid.UUID, uuid.UUID], Relation] = {}
        stmt = select(Relation).where(
            Relation.project_id == project_id,
            Relation.relation_type == "co_occurs_with",
            Relation.from_id.in_(unique_ids),
            Relation.to_id.in_(unique_ids),
        )
        for rel in self.db.execute(stmt).scalars().all():
            existing_map[(rel.from_id, rel.to_id)] = rel

        new_relations: List[Relation] = []
        edges_processed = 0

        for i, id_a in enumerate(unique_ids):
            for id_b in unique_ids[i + 1 :]:
                # Bidirectional: A -> B and B -> A
                for from_id, to_id in ((id_a, id_b), (id_b, id_a)):
                    key = (from_id, to_id)
                    existing = existing_map.get(key)
                    if existing is not None:
                        self._reinforce(existing, batch_provenance, now, temporal_step)
                    else:
                        new_rel = self._build_relation(
                            project_id, from_id, to_id, batch_provenance, now, temporal_step
                        )
                        new_relations.append(new_rel)
                        # Track so a duplicate pair within the same batch reinforces
                        # in-memory instead of creating a second row.
                        existing_map[key] = new_rel
                    edges_processed += 1

        if new_relations:
            self._persist_new_relations(new_relations)

        return edges_processed

    def _reinforce(
        self,
        existing: Relation,
        batch_provenance: dict,
        timestamp: datetime,
        temporal_step: Optional[int],
    ) -> None:
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
        if not any(p.get("batch_ts") == batch_provenance.get("batch_ts") for p in prov):
            prov.append(batch_provenance)
            # Keep last 10 evidence points
            existing.provenance = prov[-10:]

    def _build_relation(
        self,
        project_id: uuid.UUID,
        from_id: uuid.UUID,
        to_id: uuid.UUID,
        batch_provenance: dict,
        timestamp: datetime,
        temporal_step: Optional[int],
    ) -> Relation:
        return Relation(
            id=uuid.uuid4(),
            project_id=project_id,
            from_id=from_id,
            from_kind="entity",
            relation_type="co_occurs_with",
            to_id=to_id,
            to_kind="entity",
            strength=1.0,  # Initial strength
            confidence=1.0,
            provenance=[batch_provenance],
            access_count=1,
            last_accessed_at=timestamp,
            temporal_start=temporal_step,
            temporal_end=temporal_step,
        )

    def _persist_new_relations(self, relations: List[Relation]) -> None:
        bind = getattr(self.db, "bind", None)
        dialect_name = getattr(getattr(bind, "dialect", None), "name", None)
        if dialect_name != "postgresql":
            self.db.add_all(relations)
            return

        rows = [self._relation_to_row(relation) for relation in relations]
        insert_stmt = pg_insert(Relation).values(rows)
        self.db.execute(
            insert_stmt.on_conflict_do_update(
                index_elements=[
                    Relation.project_id,
                    Relation.from_id,
                    Relation.to_id,
                    Relation.relation_type,
                ],
                set_={
                    "strength": func.least(Relation.strength + 0.1, 5.0),
                    "access_count": Relation.access_count + 1,
                    "last_accessed_at": insert_stmt.excluded.last_accessed_at,
                    "temporal_start": case(
                        (Relation.temporal_start.is_(None), insert_stmt.excluded.temporal_start),
                        (insert_stmt.excluded.temporal_start.is_(None), Relation.temporal_start),
                        else_=func.least(
                            Relation.temporal_start, insert_stmt.excluded.temporal_start
                        ),
                    ),
                    "temporal_end": case(
                        (Relation.temporal_end.is_(None), insert_stmt.excluded.temporal_end),
                        (insert_stmt.excluded.temporal_end.is_(None), Relation.temporal_end),
                        else_=func.greatest(
                            Relation.temporal_end, insert_stmt.excluded.temporal_end
                        ),
                    ),
                    "provenance": case(
                        (Relation.provenance.is_(None), insert_stmt.excluded.provenance),
                        else_=Relation.provenance.op("||")(insert_stmt.excluded.provenance),
                    ),
                },
            )
        )

    @staticmethod
    def _relation_to_row(relation: Relation) -> Dict[str, object]:
        return {
            "id": relation.id,
            "project_id": relation.project_id,
            "from_id": relation.from_id,
            "from_kind": relation.from_kind,
            "relation_type": relation.relation_type,
            "to_id": relation.to_id,
            "to_kind": relation.to_kind,
            "strength": relation.strength,
            "confidence": relation.confidence,
            "provenance": relation.provenance,
            "access_count": relation.access_count,
            "last_accessed_at": relation.last_accessed_at,
            "temporal_start": relation.temporal_start,
            "temporal_end": relation.temporal_end,
        }
