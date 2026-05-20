# Synapse Engine: Memory That Learns

## Overview

The **Synapse Engine** is a new learning subsystem for Condensate that adds adaptive relationship building between memories. Positioned between the Condenser and Knowledge Graph in the pipeline, it creates "synapses" between related memories, strengthens them during retrieval, and consolidates dense clusters into higher-order memories.

**Tagline:** Memory that does not just store facts — it learns relationships.

## Architecture Integration

```
Raw Input
  ↓
Ingress Agent
  ↓
Condenser
  ↓
Synapse Engine   ← new learning subprocess
  ↓
Knowledge Graph
  ↓
Memory Router
```

## Core Components

### 1. Synapse Creation During Condensation

When the Condenser extracts entities, assertions, relations, events, learnings, and policies, the Synapse Engine emits candidate synapses:

```python
Synapse {
  from_memory_id: UUID
  to_memory_id: UUID
  relation_type: str  # co_retrieval, same_entity, same_goal, temporal_cluster, etc.
  weight: float
  evidence_ids: List[UUID]
  created_by: str  # 'condenser', 'retrieval', 'consolidation'
  decay_rate: float
  last_activated_at: datetime
}
```

**Signals for synapse creation:**
- **co_occurs**: Memories appearing in same condensation batch
- **same_entity**: Both memories reference same entity
- **same_goal**: Related to same user objective/project
- **temporal_cluster**: Memories from same time period
- **semantic_similarity**: Content similarity via embeddings

### 2. Hebbian Strengthening During Retrieval

Following "neurons that fire together, wire together," synapses are strengthened when connected memories are retrieved together:

```python
if memory_a and memory_b are retrieved together:
    synapse.weight += learning_rate * relevance_score
```

**Strengthening signals:**
- co_retrieval: Memories retrieved in same query
- same_entity: Both relevant to same entity
- same_user_goal: Both support same objective
- same_project: Related to same project context
- explicit_user_confirmation: User validates connection
- model_used_in_final_answer: Contributed to response
- temporal_proximity: Retrieved in same session

### 3. Adaptive Decay and Pruning

Background worker prevents graph bloat by decaying unused connections:

```python
every N hours:
    for synapse in synapses:
        synapse.weight *= decay_rate
        if synapse.weight < prune_threshold:
            archive_or_delete(synapse)
```

### 4. Memory Consolidation

When synapse clusters become dense, generate higher-order memories:

```python
Cluster: user prefers local-first AI infra + verifiable memory + agent portability
→ New Learning: "User values sovereign, inspectable AI memory systems over opaque SaaS memory."
```

## Implementation Plan

### Phase 1: Database Schema (Complete)

**New Tables:**
- `memory_synapses`: Core synapse storage
- `synapse_activations`: Activation history for analytics
- `consolidated_memories`: Higher-order memory storage

**Migration:** `migrations/synapse_engine_001.py`

### Phase 2: Synapse Engine Module (Complete)

**Directory:** `src/synapses/`

**Features:**
- **Multi-Signal Scoring:** Implemented Jaccard entity similarity, temporal proximity, and co-occurrence scoring with non-linear boosting in `scorer.py`.
- **Advanced Clustering:** Integrated `networkx` Louvain community detection to identify dense subgraphs of memories in `consolidation.py`.
- **LLM Synthesis:** Replaced placeholders with real `LLMClient` integration to synthesize "Policies" and "Learnings" from detected clusters.

### Phase 3: Pipeline Integration (Complete)

**Condenser Updates:**
```python
# After edge synthesis
synapse_engine = SynapseEngine(self.db)
synapse_engine.create_synapses_from_condensation(
    project_id, new_assertion_ids, temporal_step=temporal_step
)
```

### Phase 4: UI & Configuration (Complete)

**Features:**
- **Admin Dashboard Integration:** Added "Synapse Engine" settings panel to the UI (`App.jsx`) to control learning rate, decay rate, and thresholds via interactive sliders.
- **Consolidations View:** Added a dedicated "Consolidations" tab to monitor generated meta-cognitive rules and policies.
- **Persistent Settings:** Settings are persisted in `synapse_config.json` and load dynamically into `src/synapses/config.py`.


## Benefits

### Product Positioning
- **Differentiator:** Most memory systems are static; Condensate learns
- **Value Prop:** "git-like version control for AI memory" + relationship learning
- **Philosophy Alignment:** Structured before embedded → relationships before vectors

### Technical Advantages
- **Adaptive Retrieval:** Better relevance through learned connections
- **Memory Efficiency:** Pruning prevents exponential graph growth
- **Higher-Order Learning:** Automatic pattern recognition and summarization
- **Explainability:** Provenance tracking for learned relationships

## Success Metrics

- **Learning Effectiveness:** Improved retrieval relevance over time
- **Graph Health:** Stable synapse counts, bounded growth
- **Consolidation Quality:** User validation rates for generated memories
- **Performance:** <100ms latency for synapse operations

## Risk Mitigation

- **Memory Bloat:** Aggressive pruning with configurable thresholds
- **False Learning:** Confidence scoring and human validation loops
- **Performance Impact:** Async processing for heavy operations
- **Backwards Compatibility:** Feature flags and gradual rollout

## Future Extensions

- **Cross-Memory Reasoning:** Use learned synapses for multi-hop inference
- **Predictive Retrieval:** Anticipate related memories before queries
- **Memory Compression:** Use consolidated memories for storage optimization
- **Learning Analytics:** Dashboard for visualizing memory relationship graphs

---

*This document captures the Synapse Engine expansion plan for Condensate's memory learning capabilities.*