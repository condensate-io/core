# Database Schema (PostgreSQL)

This document reflects the **V2 Schema** as implemented in `src/db/models.py`.

## Core Tables

### `projects`
Root scope for all memory and knowledge.
- `id` (UUID, PK)
- `name` (VARCHAR)
- `created_at` (TIMESTAMP)

### `episodic_items`
Immutable raw record of events (chats, logs, tool outputs).
- `id` (UUID, PK)
- `project_id` (UUID, FK)
- `source` (VARCHAR) - e.g., 'chatgpt_export', 'api', 'tool', 'note'
- `occurred_at` (TIMESTAMP) - When the event happened.
- `text` (TEXT) - The raw content.
- `metadata` (JSONB) - Arbitrary source metadata.
- `qdrant_point_id` (VARCHAR) - Reference to vector store.
- `created_at` (TIMESTAMP) - When the record was ingested.

### `entities`
Canonicalized objects (People, Systems, Concepts, Artifacts).
- `id` (UUID, PK)
- `project_id` (UUID, FK)
- `type` (VARCHAR) - person, org, system, project, tool, concept, artifact.
- `canonical_name` (VARCHAR)
- `aliases` (JSONB) - List of alternative names.
- `embedding_ref` (VARCHAR) - Vector reference.
- `confidence` (FLOAT)
- `first_seen_at` / `last_seen_at` (TIMESTAMP)

### `assertions`
Structured facts distilled from Episodic Items. Links Subjects to Objects.
- `id` (UUID, PK)
- `project_id` (UUID, FK)
- `subject_entity_id` (UUID, FK, Optional)
- `subject_text` (VARCHAR) - Fallback or literal "User".
- `predicate` (VARCHAR) - prefers, uses, works_on, etc.
- `object_entity_id` (UUID, FK, Optional)
- `object_text` (VARCHAR) - Fallback or literal value.
- `polarity` (INT) - 1 for Affirmative, -1 for Negated.
- `confidence` (FLOAT)
- `status` (VARCHAR) - active, superseded, contested.
- `provenance` (JSONB) - List of evidence objects explaining the derivation.
- **Cognitive Fields**:
  - `strength` (FLOAT) - Hebbian weight (Long-Term Potentiation).
  - `access_count` (INT)
  - `last_accessed_at` (TIMESTAMP)

### `relations`
Concept-to-Concept relationships (The Ontology Graph).
- `id` (UUID, PK)
- `project_id` (UUID, FK)
- `from_id` (UUID) - Source Entity or OntologyNode.
- `from_kind` (VARCHAR) - 'entity' or 'ontology'.
- `relation_type` (VARCHAR) - is_a, part_of, co_occurs_with, related_to.
- `to_id` (UUID) - Target ID.
- `to_kind` (VARCHAR) - 'entity' or 'ontology'.
- `confidence` (FLOAT)
- `provenance` (JSONB) - Context traces.
- **Cognitive Fields**:
  - `strength` (FLOAT) - Edge weight used for Spreading Activation.
  - `access_count` (INT)
  - `last_accessed_at` (TIMESTAMP)

### `policies`
Operational rules extracted from memory.
- `id` (UUID, PK)
- `trigger` (VARCHAR) - Contextual trigger.
- `rule` (TEXT) - The instruction.
- `priority` (FLOAT)
- `scope` (VARCHAR) - global, project.
- `provenance` (JSONB) - Supporting evidence.

## Auxiliary Tables
- `ontology_nodes`: Hierarchical categories.
- `api_keys`: Auth tracking.
- `data_sources`: Ingestion configuration.
- `ingest_jobs` / `ingest_job_runs`: Pipeline tracking.
- `fetched_artifacts`: Deduplication and staging.
