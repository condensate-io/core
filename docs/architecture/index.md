# Architecture Documentation

## Overview

The **Condensates** project builds a "Memory Condensation OS" that gives AI agents structured, deterministic, and verifiable long-term memory. It replaces the "bag of text" RAG approach with a rigorous ontology of **Events**, **Learnings** (Assertions), and **Policies**.

## Core Components

### 1. Data Store (PostgreSQL)
We use PostgreSQL as the primary source of truth for:
-   **Projects**: Use scopes.
-   **Episodic Items**: Immutable log of raw events (chat, logs).
-   **Assertions**: Structured facts distilled from episodes.
-   **Policies**: Governance rules extracted from interactions.
-   **Proof Envelopes**: Cryptographic provenance for every assertion.

### 2. Vector Store (Qdrant)
Used for semantic search and deduplication:
-   **Episodic Vectors**: Embeddings of raw memories.
-   **Assertion Vectors**: Embeddings of condensed facts.

### 3. The Engines
-  - **Memory Router (`src/retrieve/router.py`)**:
    -   **Traffic Control**: Decides if a query needs "Recall" (Vector/Graph) or "Research" (Cognitive Graph).
    -   **Spreading Activation**: Traverses the concept graph using Hebbian weights to pull relevant context.
    -   **Deterministic Path**: Supports `skip_llm` to return raw facts without hallucination.
- **Condenser (`src/engine/condenser.py`)**:
    -   **Distillation**: Asynchronous pipeline that turns raw `EpisodicItems` into `Assertions`.
    -   **Edge Synthesizer**: Computes concept co-occurrence and builds the "Living Ontology".
    -   **Proof Envelopes**: Signs every generated assertion with model metadata and input hashes.
    -   **Cognitive Dynamics**: Manages activation decay and Hebbian reinforcement.

### 4. Admin Interface (React)
-   **Ontology Visualizer**: D3-powered graph representing the "mind" of the agent.
-   **LLM Configuration**: Dynamic switching between local Ollama (Phi-3) and cloud providers.

---

## Documentation

### Technical Reference
- [Database Schema](schema.md)
- [Learning System Architecture](learning_system.md)
- [MCP Server Specification](../mcp.md)
- [Edge API Reference](../api.md)

### User Guides
- [Getting Started](usage/getting_started.md)
- [Configuration Guide](usage/configuration.md)
- [Best Practices](usage/best_practices.md)

---

## Data Flow

1.  **Ingress**: `Raw Data` -> `Ingest API` -> `Episodic Store` & `Qdrant`.
2.  **Condensation**: `Scheduler` -> `Condenser` -> Reads `Unprocessed Memories` -> LLM Extraction -> Writes `Assertions` + `Proof Envelopes`.
3.  **Traffic Control Retrieval**: `Query` -> `MemoryRouter` -> (Strategy: Recall/Research) -> (Optional: LLM Synthesis) -> Response.

## Key Concepts

-   **Episodic Item**: A single event, log, or message.
-   **Assertion (Learning)**: A synthesized fact. E.g., "User prefers strictly typed Python code."
-   **Proof Envelope**: A JSON structure containing the cryptographic signature proving *why* the system believes an Assertion.
