# Specification: Cognitive Provenance

Cognitive Provenance is the ability to trace any system belief ("Learning") back to the raw observations ("Events") that justified it.

## 1. The Provenance Chain

The chain consists of three nodes:
1.  **Observation**: The raw event (e.g., User A said "The database is broken").
2.  **Inference**: The distillation process (e.g., LLM concludes "Database is unstable").
3.  **Belief**: The stored Learning (Statement: "Database is unstable", Confidence: 0.8).

## 2. Requirements

### 2.1 Backward Traceability
Every `Learning` object MUST contain a non-empty `evidence_ids` list.
-   **Violation**: A Learning without evidence is considered a "Hallucination" and must be flagged or discarded (unless manually inserted as an Axiom).

### 2.2 Forward Impact Analysis
When a `MemoryEvent` is marked as `invalid` (e.g., user retracted a statement), the system MUST identify all `Learning` objects dependent on it (where `event.id` is in `learning.evidence_ids`).
-   **Action**: Re-evaluate or downgrade confidence of dependent Learnings.

## 3. Proof Envelopes

(See RFC-0002 for implementation details)

The system SHOULD define a `ProofEnvelope` that wraps the Learning, containing:
-   Hash of inputs.
-   Model ID / Prompt Version used for distillation.
-   Signature of the Condenser Kernel.
