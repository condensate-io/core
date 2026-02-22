from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from typing import List, Dict, Any, Set
import uuid
import math
from src.db.models import Relation, Assertion, Entity

class CognitiveService:
    def __init__(self, db: Session):
        self.db = db

    def hebbian_update(self, node_ids: List[uuid.UUID]):
        """
        "Neurons that fire together, wire together."
        
        If multiple nodes (Entities/Assertions) are retrieved in the same context,
        we strengthen the relations between them.
        """
        if len(node_ids) < 2:
            return

        now = datetime.utcnow()
        
        # 1. Update access stats for the activated nodes themselves
        self.db.query(Assertion).filter(Assertion.id.in_(node_ids)).update(
            {
                Assertion.access_count: Assertion.access_count + 1,
                Assertion.last_accessed_at: now
            },
            synchronize_session=False
        )
        self.db.query(Entity).filter(Entity.id.in_(node_ids)).update(
            {
                # Note: Entity model doesn't have access_count in the provided model, but it has last_seen_at
                Entity.last_seen_at: now
            },
            synchronize_session=False
        )

        # 2. Extract Entity IDs if Assertion IDs were passed
        # This allows hebbian reinforcement to flow from retrieved facts down to concepts
        assertions = self.db.query(Assertion).filter(Assertion.id.in_(node_ids)).all()
        entity_ids_from_assertions = set()
        for a in assertions:
            if a.subject_entity_id: entity_ids_from_assertions.add(a.subject_entity_id)
            if a.object_entity_id: entity_ids_from_assertions.add(a.object_entity_id)
        
        # Combine all relevant IDs for relation strengthening
        all_ids = set(node_ids) | entity_ids_from_assertions
        
        # 3. Strengthen connections between co-activated nodes
        # Find existing relations where BOTH sides are in the co-activated set
        relations = self.db.query(Relation).filter(
            Relation.from_id.in_(all_ids),
            Relation.to_id.in_(all_ids)
        ).all()
        
        for rel in relations:
            # Increase strength (Simple linear reinforcement with cap)
            rel.strength = min(rel.strength + 0.1, 5.0) 
            rel.last_accessed_at = now
            rel.access_count += 1
        
        self.db.commit()

    def spreading_activation(self, seed_ids: List[uuid.UUID], decay_factor: float = 0.5, steps: int = 2) -> Set[uuid.UUID]:
        """
        Traverse the graph from seed nodes, activating neighbors based on edge strength.
        Returns a set of activated node IDs (including seeds).
        """
        activated = set(seed_ids)
        current_frontier = set(seed_ids)
        
        for _ in range(steps):
            if not current_frontier:
                break
                
            next_frontier = set()
            
            # Find all outgoing relations from current frontier
            # Filter by strength > threshold to propagate
            relations = self.db.query(Relation).filter(
                Relation.from_id.in_(current_frontier),
                Relation.strength > 0.8  # Threshold
            ).all()
            
            for rel in relations:
                if rel.to_id not in activated:
                    activated.add(rel.to_id)
                    next_frontier.add(rel.to_id)
            
            current_frontier = next_frontier
            
        return activated

    def apply_activation_decay(self, decay_rate: float = 0.05):
        """
        Background maintenance task.
        A(t) = A0 * e^(-lambda * t)
        
        Reduces strength of Relations that haven't been accessed recently.
        """
        now = datetime.utcnow()
        # Find relations not accessed in the last 24 hours
        # We decrease strength by decay_rate
        # Sub-queries or batch updates depending on DB scale.
        # For this phase, we use a simple update statement.
        
        # Strength = max(0.1, Strength - decay_rate)
        # We only decay if not recently accessed
        self.db.query(Relation).filter(
            Relation.last_accessed_at < now,
            Relation.strength > 0.1
        ).update(
            {
                Relation.strength: Relation.strength - decay_rate
            },
            synchronize_session=False
        )
        self.db.commit()

    def reinforce_co_retrieval(self, item_ids: List[uuid.UUID]):
        """
        Hebbian reinforcement for items retrieved together in a query response.
        Similar to hebbian_update but specifically for query-time co-activation.
        """
        self.hebbian_update(item_ids)
