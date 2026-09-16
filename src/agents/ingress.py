import logging
import uuid
import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from qdrant_client import QdrantClient
from qdrant_client.http import models

from src.db.models import EpisodicItem, Project
from src.db.schemas import EpisodicItemCreate
from src.engine.embedding import get_embedding_model

logger = logging.getLogger("IngressAgent")


class IngressAgent:
    def __init__(self, db: Session, qdrant: QdrantClient):
        self.db = db
        self.qdrant = qdrant
        # Shared, process-wide embedding model singleton (see src/engine/embedding.py).
        # Reused across IngressAgent instances so a fresh condensation batch
        # never re-pays ONNX model load cost, and always matches the model
        # used at query time in src/retrieve/router.py.
        self.embedding_model = get_embedding_model()

    def process_memory(self, data: EpisodicItemCreate) -> EpisodicItem:
        """
        Clean, Validate, and Store a new episodic item.
        """
        return self._process_memory_batch([data])[0]

    def _resolve_project_id(self, raw_project_id: str) -> uuid.UUID:
        try:
            return uuid.UUID(raw_project_id)
        except ValueError:
            # Handle name-based lookup or generation
            return uuid.uuid5(uuid.NAMESPACE_DNS, raw_project_id)

    def _ensure_projects(self, batch_data: List[EpisodicItemCreate]) -> Dict[str, uuid.UUID]:
        """Resolve + auto-create all projects referenced by a batch in one round trip."""
        project_ids: Dict[str, uuid.UUID] = {}
        for data in batch_data:
            project_ids[data.project_id] = self._resolve_project_id(data.project_id)

        unique_uuids = list(set(project_ids.values()))
        existing = self.db.query(Project).filter(Project.id.in_(unique_uuids)).all()
        existing_ids = {p.id for p in existing}

        missing = [
            Project(id=puid, name=raw_id)
            for raw_id, puid in project_ids.items()
            if puid not in existing_ids
        ]
        # Dedup missing (multiple raw ids could map to the same uuid5)
        seen = set()
        to_add = []
        for proj in missing:
            if proj.id not in seen:
                seen.add(proj.id)
                to_add.append(proj)

        if to_add:
            for proj in to_add:
                logger.info(f"Auto-creating project {proj.name}")
            self.db.add_all(to_add)
            self.db.commit()

        return project_ids

    def _process_memory_batch(self, batch_data: List[EpisodicItemCreate]) -> List[EpisodicItem]:
        """
        Store + embed a batch of episodic items with a single embedding call
        and a single Qdrant upsert, instead of one round trip per item.
        """
        if not batch_data:
            return []

        # 1. Resolve/auto-create all referenced projects up front (one query)
        project_ids = self._ensure_projects(batch_data)

        # 2. Batch-generate vectors for the whole chunk in one embedding call
        texts = [data.text for data in batch_data]
        vectors = [v.tolist() for v in self.embedding_model.embed(texts)]

        # 3. Build all EpisodicItem rows and bulk-insert
        new_items: List[EpisodicItem] = []
        for data in batch_data:
            item_id = uuid.uuid4()
            new_items.append(
                EpisodicItem(
                    id=item_id,
                    project_id=project_ids[data.project_id],
                    source=data.source,
                    text=data.text,
                    metadata_=data.metadata,
                    occurred_at=data.occurred_at or datetime.datetime.utcnow(),
                    qdrant_point_id=str(item_id),
                )
            )

        self.db.add_all(new_items)
        self.db.commit()

        # 4. Single batched Qdrant upsert for the whole chunk
        try:
            points = [
                models.PointStruct(
                    id=str(item.id),
                    vector=vector,
                    payload={
                        "text": item.text,
                        "project_id": str(item.project_id),
                        "source": item.source,
                        "metadata": item.metadata_,
                        "occurred_at": item.occurred_at.isoformat(),
                    },
                )
                for item, vector in zip(new_items, vectors)
            ]
            self.qdrant.upsert(collection_name="episodic_chunks", points=points)
        except Exception as e:
            logger.error(f"Failed to upsert batch to Qdrant: {e}")
            # Identify if we should rollback Postgres?
            # For now, we keep it in PG.

        return new_items

    async def process_and_condense(self, data: EpisodicItemCreate) -> EpisodicItem:
        """
        Full pipeline entry point: store + embed, then run the complete
        condensation pipeline (NER → EntityCanonicalizer → EdgeSynthesizer
        → optional LLM extraction → GuardrailEngine → Assertions/Relations).
        """
        return (await self.process_and_condense_batch([data]))[0]

    async def process_and_condense_batch(self, batch_data: List[EpisodicItemCreate]) -> List[EpisodicItem]:
        """
        Process multiple items at once to optimize throughput.
        Large batches are split to avoid OOM during NER + LLM condensation.
        """
        import os

        chunk_size = max(1, int(os.getenv("CONDENSE_BATCH_SIZE", "40")))
        all_items: List[EpisodicItem] = []

        for offset in range(0, len(batch_data), chunk_size):
            chunk = batch_data[offset : offset + chunk_size]
            items = self._process_memory_batch(chunk)

            if not items:
                continue

            try:
                from src.engine.condenser import Condenser

                condenser = Condenser(self.db)
                await condenser.distill(items[0].project_id, items)
            except Exception as e:
                logger.error(
                    "Batch condensation failed for chunk %s-%s: %s",
                    offset,
                    offset + len(chunk),
                    e,
                )

            all_items.extend(items)

        return all_items

