import math
from typing import List, Dict, Any, Optional

class SynapseScorer:
    @staticmethod
    def score_co_occurs(count: int) -> float:
        """Score based on how many times memories appear together in a batch."""
        # Logarithmic scaling: 1->0.2, 2->0.4, 5->0.7, 10->0.9
        if count <= 0: return 0.0
        return min(0.1 + 0.3 * math.log2(count + 1), 1.0)

    @staticmethod
    def score_entity_jaccard(entities_a: List[str], entities_b: List[str]) -> float:
        """Jaccard similarity of entities between two memories."""
        if not entities_a or not entities_b:
            return 0.0
        set_a, set_b = set(entities_a), set(entities_b)
        intersection = len(set_a.intersection(set_b))
        union = len(set_a.union(set_b))
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def score_temporal_proximity(step_a: Optional[int], step_b: Optional[int], max_delta: int = 10) -> float:
        """Score based on how close memories are in time (simulation steps)."""
        if step_a is None or step_b is None:
            return 0.0
        delta = abs(step_a - step_b)
        if delta > max_delta:
            return 0.0
        return 1.0 - (delta / max_delta)

    @staticmethod
    def calculate_initial_weight(signals: Dict[str, float]) -> float:
        """Combine multiple signals into a single initial weight with boosting."""
        # Configurable weights for different signals
        weights = {
            "co_occurs": 0.4,
            "same_entity": 0.5,
            "entity_jaccard": 0.7,
            "temporal_proximity": 0.4,
            "semantic_similarity": 0.8,
            "same_goal": 0.6
        }
        
        total_score = 0.0
        total_weight = 0.0
        active_signals = 0
        
        for signal, score in signals.items():
            if signal in weights and score > 0:
                total_score += score * weights[signal]
                total_weight += weights[signal]
                active_signals += 1
        
        if total_weight == 0:
            return 0.05
            
        base_weight = total_score / total_weight
        
        # Multi-signal boost: if we have multiple strong signals, increase confidence
        if active_signals > 1:
            boost = 0.1 * (active_signals - 1)
            base_weight = min(base_weight + boost, 1.0)
            
        return base_weight
