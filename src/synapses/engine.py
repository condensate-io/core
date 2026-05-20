import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, update

from src.synapses.models import Synapse, SynapseActivation
from src.synapses.scorer import SynapseScorer
from src.synapses.config import synapse_config

class SynapseEngine:
    def __init__(self, db: Session):
        self.db = db
        self.scorer = SynapseScorer()

    def create_synapses_from_condensation(self, project_id: uuid.UUID, assertion_ids: List[uuid.UUID], temporal_step: Optional[int] = None) -> int:
        """
        Evaluate extracted data and create synapses between related memories.
        """
        if not synapse_config.ENABLED or len(assertion_ids) < 2:
            return 0

        synapse_count = 0
        from src.db.models import Assertion
        
        # 1. Fetch the actual assertions to analyze their content
        stmt = select(Assertion).where(Assertion.id.in_(assertion_ids))
        assertions = self.db.execute(stmt).scalars().all()
        
        # 2. Analyze pairs of assertions for relationships
        for i in range(len(assertions)):
            for j in range(i + 1, len(assertions)):
                a1, a2 = assertions[i], assertions[j]
                
                signals = {}
                
                # Signal: Co-occurrence (They are in the same batch)
                signals["co_occurs"] = 1.0 
                
                # Signal: Shared Entities
                entities1 = [str(id) for id in [a1.subject_entity_id, a1.object_entity_id] if id]
                entities2 = [str(id) for id in [a2.subject_entity_id, a2.object_entity_id] if id]
                
                jaccard = self.scorer.score_entity_jaccard(entities1, entities2)
                if jaccard > 0:
                    signals["entity_jaccard"] = jaccard
                
                # Signal: Temporal Proximity
                if temporal_step is not None:
                    # In this context, they both share the same temporal_step
                    signals["temporal_proximity"] = 1.0
                
                # Signal: Semantic Similarity (Placeholder for embedding check)
                # In a real system, we'd compare their embeddings if available
                
                # 3. Calculate initial weight
                weight = self.scorer.calculate_initial_weight(signals)
                
                if weight > synapse_config.PRUNE_THRESHOLD:
                    # 4. Create Synapse
                    new_synapse = Synapse(
                        project_id=project_id,
                        from_memory_id=a1.id,
                        to_memory_id=a2.id,
                        relation_type="batch_correlation",
                        weight=weight,
                        created_by="condenser",
                        decay_rate=synapse_config.DECAY_RATE,
                        last_activated_at=datetime.utcnow()
                    )
                    self.db.add(new_synapse)
                    synapse_count += 1
        
        self.db.commit()
        return synapse_count

    def strengthen_on_retrieval(self, source_ids: List[uuid.UUID], query: str) -> int:
        """
        Apply Hebbian strengthening to synapses connecting co-retrieved memories.
        """
        if not synapse_config.ENABLED or len(source_ids) < 2:
            return 0

        updated_count = 0
        # Strengthen every pair of co-retrieved memories
        for i in range(len(source_ids)):
            for j in range(i + 1, len(source_ids)):
                id_a, id_b = source_ids[i], source_ids[j]
                
                # Find existing synapse or create one (co-retrieval)
                # We check both directions
                stmt = select(Synapse).where(
                    ((Synapse.from_memory_id == id_a) & (Synapse.to_memory_id == id_b)) |
                    ((Synapse.from_memory_id == id_b) & (Synapse.to_memory_id == id_a))
                )
                synapse = self.db.execute(stmt).scalars().first()
                
                if synapse:
                    # Neurons that fire together, wire together
                    synapse.weight = min(synapse.weight + synapse_config.LEARNING_RATE, 1.0)
                    synapse.last_activated_at = datetime.utcnow()
                    
                    # Record activation
                    activation = SynapseActivation(
                        synapse_id=synapse.id,
                        relevance_score=1.0, # Could be more dynamic
                        context_query=query
                    )
                    self.db.add(activation)
                    updated_count += 1
                else:
                    # Create new co-retrieval synapse
                    new_synapse = Synapse(
                        project_id=self.get_project_id_for_memory(id_a), # Helper needed
                        from_memory_id=id_a,
                        to_memory_id=id_b,
                        relation_type="co_retrieval",
                        weight=synapse_config.LEARNING_RATE,
                        created_by="retrieval",
                        decay_rate=synapse_config.DECAY_RATE,
                        last_activated_at=datetime.utcnow()
                    )
                    self.db.add(new_synapse)
                    updated_count += 1
        
        self.db.commit()
        return updated_count

    def get_project_id_for_memory(self, memory_id: uuid.UUID) -> uuid.UUID:
        """Helper to find the project_id for a given memory (Assertion)."""
        # In a real system, we'd query the 'assertions' table
        from src.db.models import Assertion
        stmt = select(Assertion.project_id).where(Assertion.id == memory_id)
        result = self.db.execute(stmt).scalars().first()
        return result or uuid.uuid4() # Fallback
