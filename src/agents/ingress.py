import logging
import uuid
import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from qdrant_client import QdrantClient
from qdrant_client.http import models
from fastembed import TextEmbedding

from src.db.models import EpisodicItem, Project
from src.db.schemas import EpisodicItemCreate

logger = logging.getLogger("IngressAgent")

class IngressAgent:
    def __init__(self, db: Session, qdrant: QdrantClient):
        self.db = db
        self.qdrant = qdrant
        # Initialize embedding model (using fastembed as per requirements)
        self.embedding_model = TextEmbedding()

    def process_memory(self, data: EpisodicItemCreate) -> EpisodicItem:
        """
        Clean, Validate, and Store a new episodic item.
        """
        # 1. Resolve Project ID
        try:
            project_uuid = uuid.UUID(data.project_id)
        except ValueError:
            # Handle name-based lookup or generation
            project_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, data.project_id)
            
        # Ensure Project Exists (Optional safe-guard)
        project = self.db.query(Project).filter(Project.id == project_uuid).first()
        if not project:
            logger.info(f"Auto-creating project {data.project_id}")
            project = Project(id=project_uuid, name=data.project_id)
            self.db.add(project)
            self.db.commit()

        # 2. Generate Vectors (for episodic_chunks)
        vector_generator = self.embedding_model.embed([data.text])
        vector = list(vector_generator)[0].tolist()
        
        # 3. Store in Postgres
        item_id = uuid.uuid4()
        new_item = EpisodicItem(
            id=item_id,
            project_id=project_uuid,
            source=data.source,
            text=data.text,
            metadata_=data.metadata,
            occurred_at=data.occurred_at or datetime.datetime.utcnow(),
            qdrant_point_id=str(item_id)
        )
        self.db.add(new_item)
        self.db.commit()
        self.db.refresh(new_item)
        
        # 4. Store in Qdrant (episodic_chunks)
        try:
            self.qdrant.upsert(
                collection_name="episodic_chunks",
                points=[
                    models.PointStruct(
                        id=str(item_id),
                        vector=vector,
                        payload={
                            "text": data.text,
                            "project_id": str(project_uuid),
                            "source": data.source,
                            "metadata": data.metadata,
                            "occurred_at": new_item.occurred_at.isoformat()
                        }
                    )
                ]
            )
        except Exception as e:
            logger.error(f"Failed to upsert to Qdrant: {e}")
            # Identify if we should rollback Postgres? 
            # For now, we keep it in PG.
            
        return new_item

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
        """
        items = []
        for data in batch_data:
            items.append(self.process_memory(data))

        if not items:
            return []

        # Step 2: Run condensation pipeline on the entire batch
        try:
            from src.engine.condenser import Condenser
            condenser = Condenser(self.db)
            # Use project_id from first item (assuming all in batch share one project)
            await condenser.distill(items[0].project_id, items)
        except Exception as e:
            logger.error(f"Batch condensation failed: {e}")
            
        return items
