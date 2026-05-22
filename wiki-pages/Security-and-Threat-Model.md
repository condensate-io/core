# Security and Threat Model

Condensate is designed to operate as the central nervous system for multi-agent swarms. Because it handles highly sensitive cognitive data and system states, security and data sovereignty are foundational to its architecture.

---

## 🛡️ Proof Envelopes (Data Provenance)

A core failure mode of modern AI systems is hallucination disguised as fact. Condensate mitigates this at the storage layer via **Proof Envelopes**.

Every episodic item and condensed assertion stored in Condensate is wrapped in a Proof Envelope. This envelope contains an HMAC signature cryptographically binding the data to its origin (the specific agent, tool, or user that produced it). 

This creates a verifiable **Merkle-DAG** (Directed Acyclic Graph). If an agent attempts to alter a historical memory, or if the underlying storage is tampered with, the cryptographic signature breaks. This guarantees that your agents are making decisions based on verified, untampered historical context.

---

## 🚦 Guardrail Engine

Autonomous agents often process untrusted external inputs. Condensate includes an inline **Guardrail Engine** to protect the cognitive pipeline:

- **InstructionDetector**: Scans incoming episodic memories for prompt injection attempts or malicious payload delivery before they are condensed into the main graph.
- **ContentSafetyFilter**: Flags and segregates sensitive, PII, or unsafe content based on configurable thresholds.

These filters run *before* the L3 condenser pipeline, ensuring that toxic or malicious instructions do not pollute the canonical knowledge graph.

---

## 🏢 Multi-Tenant Isolation

Condensate is designed to run locally or in a multi-tenant cloud environment safely.

- **API Key Scoping**: Every API request must be authenticated with an API Key. This key is strictly bound to a specific `project_id`.
- **Hard Isolation**: All database queries and vector searches are strictly filtered by the associated `project_id` at the lowest level of the ORM and vector client. It is impossible for one agent swarm to read or mutate the memories of another.

---

## 🗑️ Cascade Vector Deletions

Data lifecycle management is critical. When a project is purged (e.g., via the Admin dashboard or API):

1. The project record is deleted from PostgreSQL.
2. PostgreSQL cascades the deletion to all child tables (Episodic Items, Entities, Relations, Assertions).
3. Condensate simultaneously dispatches a cascade purge to Qdrant, guaranteeing that all vector embeddings associated with that `project_id` are permanently destroyed across all collections (`episodic_chunks`, `memories`, etc.).

---

## 🏠 Data Sovereignty

Unlike proprietary memory APIs (where your agent's cognitive graph is locked in a vendor's silo), Condensate is **local-first and self-hosted**.

Your data never leaves your infrastructure unless you explicitly configure an external LLM provider for the condensation pipeline. Even then, you can swap out the LLM for local inference (e.g., via Ollama) to achieve 100% air-gapped data sovereignty. This prevents [[The-Problem#vendor-lock-in|Vendor Lock-In]] and ensures full compliance with strict data residency requirements.
