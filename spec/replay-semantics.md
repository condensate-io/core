# Specification: Replay Semantics & Determinism

To ensure the system is deterministic and debuggable, we define "Replay Semantics" and "Traffic Control" protocols.

## 1. Idempotency

The **Condensation function** `F(EpisodicItems, Ontology) -> Assertions` must be practically idempotent.
-   Running the condensation job twice on the exact same set of Items should yield the exact same Assertions (assuming the LLM seed is fixed or temperature is 0).

## 2. Deterministic Identifiers

-   **Content Hashing**: Item IDs should ideally be derived from their content hash (UUID v5) to prevent duplicates.
-   **Stable Sort**: When processing items, they must be sorted by `occurred_at` deterministically before being fed to the prompt.

## 3. Traffic Control (Deterministic Retrieval)

To guarantee reliability and verify that the system is not "hallucinating" or over-relying on LLMs during retrieval:

### 3.1 The "Recall" Path
If a query matches a high-confidence Vector Search or Graph Traversal result effectively, the system MUST support a **No-LLM** path.
-   **Flag**: `skip_llm=True`
-   **Behavior**: The Router returns the raw context (Context + Sources) without passing it to `_synthesize`.
-   **Verification**: The prompt can be re-run with `skip_llm=True` to see exactly what "knowledge" the LLM would have seen.

### 3.2 Route Transparency
Every response MUST include metadata indicating the "Route" taken:
-   `strategy`: `recall` (Vector), `research` (Graph+Vector), or `reason` (LLM-heavy).
-   `synthesized`: Boolean (True if LLM generated the final text).

## 4. Replay Scenarios

### 4.1 Schema Migration
When the `Memory Schema` changes (e.g., adding a new field to `Assertion`), the system MUST be able to regenerate the entire Semantic Memory store from the raw Episodic Memory store.

### 4.2 Model Upgrade
When upgrading the underlying LLM (e.g., GPT-4 -> GPT-5), we trigger a "re-distillation" of all active assertions to improve accuracy/nuance.
