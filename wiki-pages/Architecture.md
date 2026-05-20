# Architecture

> Condensate treats memory not as text retrieval, but as a living graph of causal events and assertions.

This page describes the core technical architecture of Condensate — from the immutable data structures that guarantee provenance to the processing pipeline that transforms raw text into structured, verifiable knowledge.

---

## Overview

Condensate's architecture is organized into six layers, each with a distinct responsibility:

```
Raw Input (Chat / Docs / API)
        │
        ▼
   [Ingress Agent]  ──── stores EpisodicItem + vector embedding
        │
        ▼
   [Condenser]      ──── NER → LLM Extraction → Entity Canonicalization
        │                → Assertion Consolidation → Edge Synthesis
        ▼
   [Synapse Engine] ──── Multi-Signal Scoring → Cluster Detection
        │                → LLM High-Fidelity Consolidation
        ▼
   [Knowledge Graph] ─── Entities, Assertions, Relations (Postgres)
        │
        ▼
   [Memory Router]  ──── Vector search + Graph traversal + Hebbian updates
        │
        ▼
   [MCP / API]      ──── Agents, SDKs, Admin Dashboard
```

---

## 1. Cryptographically-Signed Merkle-DAGs

At the foundation of Condensate is an immutable **Directed Acyclic Graph (DAG)**. This is not a bag of words — it is a **verifiable causal graph** where every node represents a semantic snapshot and every edge represents a causal relationship.

### Node Structure

Each node in the DAG defines:

| Field | Description |
|-------|-------------|
| `parents` | Array of hashes pointing to causal ancestors |
| `payload` | Semantic operations — entities, intents, state diffs (JSON) |
| `signature` | Ed25519 signature from the authoring agent's key pair |
| `hash` | SHA-256 hash of the deterministic serialization |

```typescript
interface CondensateNode {
  hash: string;         // SHA-256 of the payload
  parents: string[];    // Causal ancestor hashes
  payload: Operation[]; // Semantic diff (intent, entities, action)
  signature: string;    // Ed25519 author signature
}
```

### Why Merkle-DAGs?

- **Tamper Evidence:** Any modification to historical data invalidates cryptographic signatures down the chain.
- **Causal Ordering:** Edges represent temporal and logical sequences, not just similarity.
- **Deterministic Resolution:** The graph resolves to the latest verifiable ground truth — not the latest write.

---

## 2. Conflict-Free Replicated Data Types (CRDTs)

When multiple agents modify the same parent state concurrently — without network communication — they create a "branch" in the DAG. When the swarm syncs, these branches merge **deterministically**.

Condensate achieves **Strong Eventual Consistency (SEC)** via CRDTs:

- **Causal Ordering:** Events are ordered topologically based on DAG edges.
- **Deterministic Merge:** For operations at the same logical timestamp, lexical ordering of Lamport Clocks and author public keys dictates the final merged state — no locks, no data loss, no Last-Write-Wins.
- **Decentralized Concurrency:** Every agent runtime maintains a complete replica of its relevant memory graph. Reads and writes execute locally with zero network latency.

This architecture solves the fundamental concurrency problem that plagues centralized master-slave databases in multi-agent environments. See [[The Problem]] for why this matters.

---

## 3. The Condenser Pipeline

The Condenser is the core extraction engine that transforms raw text into structured knowledge. It operates as a deterministic, multi-stage pipeline.

### L3 — Deterministic Extraction (No-LLM Path)

The first layer runs entirely without LLM calls, ensuring speed and determinism:

1. **Named Entity Recognition (NER):** GLiNER ModernBERT models identify canonical entities (People, Organizations, Systems, Concepts) in real-time as episodic logs are ingested.
2. **Entity Canonicalization:** Extracted entities are resolved against existing canonical entries, merging aliases and deduplicating references.
3. **Semantic Edge Linking:** Relations between entities are synthesized based on co-occurrence, shared context, and explicit predicates.

**Performance:** < 15ms extraction overhead per chunk.

### L2 — LLM Enrichment Pipeline

When `LLM_ENABLED=true`, a second layer uses an OpenAI-compatible model to perform higher-fidelity extraction:

1. **Assertion Extraction:** The LLM distills structured claims (subject → predicate → object) from raw text, producing typed `Assertion` objects.
2. **Assertion Consolidation:** New assertions are compared against existing knowledge to detect contradictions, confirmations, and supersessions.
3. **Policy Synthesis:** Operational rules and governance constraints are extracted and scored by priority.

The extraction output is validated against strict JSON schemas (`ExtractionBundle` via Pydantic) before any data touches the knowledge graph.

### Pipeline Integration

After edge synthesis, the [[Synapse Engine]] receives the new assertion IDs and creates weighted connections:

```python
synapse_engine = SynapseEngine(self.db)
synapse_engine.create_synapses_from_condensation(
    project_id, new_assertion_ids, temporal_step=temporal_step
)
```

---

## 4. Proof Envelopes — Cryptographic Provenance

Every `Assertion` in Condensate is wrapped in a **Proof Envelope** — a cryptographic binding that traces the assertion back to its source observations with tamper-evident certainty.

### Envelope Structure

```json
{
  "payload": {
    "assertion_id": "uuid",
    "subject_text": "prod-db",
    "predicate": "is",
    "object_text": "read-only",
    "distilled_at": "2026-02-17T12:00:00Z"
  },
  "provenance": {
    "method": "llm-distillation",
    "model": "gpt-4-turbo",
    "input_hashes": [
      "sha256(item_1_text)",
      "sha256(item_2_text)"
    ]
  },
  "signature": "hmac_sha256(payload + provenance, CONDENSATE_SECRET)"
}
```

### How It Works

1. **Hashing:** All `EpisodicItem` content is hashed (SHA-256) upon ingress.
2. **Linking:** When the Condenser generates an Assertion, it cites the source `item_id`s.
3. **Signing:** The system computes an HMAC-SHA256 signature over the payload and provenance using `CONDENSATE_SECRET`.
4. **Verification:** Before an agent uses an Assertion, the system verifies the signature to ensure the statement hasn't been altered without re-distillation.

### Deterministic Replay

Proof Envelopes enable **deterministic replay** — re-running the distillation job on the same `input_hashes` with the same model to verify output consistency within semantic similarity bounds.

→ Full specification: [RFC 0002: Proof Envelope](https://github.com/condensate-io/core/blob/main/rfcs/0002-proof-envelope.md)

---

## 5. Entity Canonicalization and Semantic Edge Linking

Condensate maintains a canonical knowledge graph built on resolved entities and typed relationships.

### Memory Schema (V2)

The cognitive memory system is built on 8 core tables:

| Table | Purpose |
|-------|---------|
| **Project** | Root scope for all memory — multi-tenant isolation boundary |
| **EpisodicItem** | Immutable log of raw events, conversations, observations |
| **Entity** | Resolved canonical objects (Person, Org, System, Concept) |
| **Assertion** | Structured claims with polarity, confidence, and Hebbian strength |
| **Event** | Significant temporal occurrences distilled from episodic streams |
| **OntologyNode** | Abstract concepts and taxonomy categories |
| **Relation** | Typed edges between entities and ontology nodes |
| **Policy** | Operational governance rules extracted from memory |

### Cognitive Dynamics

Both Assertions and Relations carry Hebbian dynamics:

- `strength` — Long-Term Potentiation weight, increased by retrieval
- `access_count` — How often the memory has been activated
- `last_accessed_at` — Temporal recency for decay calculations

These fields power the [[Synapse Engine]]'s adaptive learning.

---

## 6. Multi-Tenant Scoping

Condensate enforces strict project-level isolation via API keys:

- Every API key is scoped to one or more **Projects**.
- All queries, ingestion operations, and graph traversals are filtered by project scope.
- **Cascade vector deletions:** When a project is purged, all associated Qdrant vectors are deleted alongside the relational data — no orphaned embeddings.
- The Admin Dashboard (`http://localhost:3010`) provides project and API key management.

→ Security deep dive: [[Security and Threat Model]]

---

## Storage Layer

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Structured Storage | PostgreSQL 15 | Entities, Assertions, Relations, Policies, Synapses |
| Vector Storage | Qdrant | Embedding-based similarity search over episodic chunks |
| Local LLM | Ollama | On-premise inference for extraction and consolidation |
| Admin UI | React (port 3010) | Dashboard for project management, API keys, synapse settings |

---

## Further Reading

- [[Synapse Engine]] — Active learning, Hebbian strengthening, and memory consolidation
- [[The Problem]] — The failure modes that motivated this architecture
- [[Security and Threat Model]] — Threat analysis and defense mechanisms
- [[Getting Started]] — Run the full stack locally
