# Specification: Memory Schema (V2)

This document serves as the **Source of Truth** for the data model of the Condensate system (V2). All implementations must adhere to this schema.

## 1. Domain Model

The Cognitive Memory System is built on 8 core tables that represent the "Mental Model" of the agent.

### 1.1 Project (Scope)
Root scope for all memory and knowledge.
- `id`: UUID (Primary Key)
- `name`: String
- `created_at`: Datetime

### 1.2 EpisodicItem (Raw Memory)
Immutable log of raw events, conversations, and observations.
- `id`: UUID
- `project_id`: UUID (FK)
- `source`: String (e.g., `chatgpt_export`, `api`, `tool`, `note`)
- `text`: Text (The raw content)
- `occurred_at`: Datetime (When it happened)
- `metadata`: JSONB (Arbitrary source details)
- `qdrant_point_id`: String (Vector Store reference)

### 1.3 Entity (Canonical Objects)
Resolved entities (People, Organizations, Systems, Concepts).
- `id`: UUID
- `project_id`: UUID (FK)
- `type`: String (`person`, `org`, `system`, `tool`, `concept`, etc.)
- `canonical_name`: String
- `aliases`: List[String]
- `confidence`: Float

### 1.4 Assertion (Knowledge Graph)
Structured claims or facts derived from Episodic Items.
- `id`: UUID
- `project_id`: UUID (FK)
- `subject_entity_id`: UUID (FK, Optional)
- `subject_text`: String (Fallback if no Entity)
- `predicate`: String (e.g., `prefers`, `uses`, `is_a`)
- `object_entity_id`: UUID (FK, Optional)
- `object_text`: String (Fallback)
- `polarity`: Int (1 = Affirm, -1 = Negated)
- `confidence`: Float
- `status`: String (`active`, `superseded`, `contested`)
- `provenance`: JSONB List (References to `EpisodicItem.id` and quotes)
- **Cognitive Dynamics**:
  - `strength`: Float (Hebbian weight / Long-Term Potentiation)
  - `access_count`: Integer
  - `last_accessed_at`: Datetime

### 1.5 Event (Temporal)
Significant occurrences distilled from episodic streams.
- `id`: UUID
- `project_id`: UUID (FK)
- `type`: String (`meeting`, `deployment`, `incident`)
- `summary`: Text
- `participants`: JSONB List (Entity Refs)
- `occurred_at`: Datetime

### 1.6 OntologyNode (Taxonomy)
Abstract concepts and categories for organizing knowledge.
- `id`: UUID
- `project_id`: UUID (FK)
- `label`: String
- `node_type`: String (`concept`, `category`)
- `parent_ids`: List[UUID]
- `confidence`: Float
- `provenance`: JSONB List

### 1.7 Relation (Edges)
Typed edges between Entities and/or Ontology Nodes.
- `id`: UUID
- `project_id`: UUID (FK)
- `from_id`: UUID
- `from_kind`: String (`entity` | `ontology`)
- `relation_type`: String (`is_a`, `part_of`, `co_occurs_with`, `related_to`)
- `to_id`: UUID
- `to_kind`: String (`entity` | `ontology`)
- `confidence`: Float
- `provenance`: JSONB List
- **Cognitive Dynamics**:
  - `strength`: Float (Hebbian weight)
  - `access_count`: Integer
  - `last_accessed_at`: Datetime

### 1.8 Policy (Governance)
Operational rules and constraints extracted from memory.
- `id`: UUID
- `project_id`: UUID (FK)
- `trigger`: String (Context trigger)
- `rule`: Text (The instruction)
- `priority`: Float
- `scope`: String (`global`, `project`)
- `provenance`: JSONB List (References to `EpisodicItem.id` and quotes, plus Proof Envelope)

## 2. Vector Store Schema (Qdrant)

### Collection: `episodic_chunks`
- **Vector**: 1536d (OpenAI / FastEmbed)
- **Payload**:
  - `project_id`: String
  - `source`: String
  - `occurred_at`: ISO Timestamp
  - `text`: String

## 3. JSON Validation

See `src/llm/schemas.py` for Pydantic models enforcing strict extraction contracts (`ExtractionBundle`) that map to these tables.
