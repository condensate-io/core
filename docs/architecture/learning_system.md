# Learning System Architecture

## Core Concepts

### 1. Memory (The Raw Input)
-   **Definition**: A discrete unit of experience. A chat message, a log entry, a document snippet.
-   **Properties**:
    -   `content`: The raw text.
    -   `vector`: Embedding of the content.
    -   `timestamp`: When it happened.
    -   `source`: Where it came from (e.g., "chat-session-123").
    -   `metadata`: arbitrary JSON (user_id, project_id, etc.).

### 2. Learning (The Condensate)
-   **Definition**: A synthesized insight or pattern derived from multiple Memories.
-   **Properties**:
    -   `statement`: A concise natural language statement of the learning (e.g., "User prefers detailed Python type hints").
    -   `confidence`: 0.0 to 1.0 score.
    -   `frequency`: How often this pattern has been observed.
    -   `vector`: Embedding of the statement.
    -   `evidence`: Links to the `Memory` IDs that support this learning.

### 3. Ontology (The Structure)
-   **Definition**: A graph of concepts and their relationships.
-   **Nodes**: Concepts (e.g., "Python", "Database", "Project X").
-   **Edges**: Relationships (e.g., "Project X" USES "PostgreSQL").
-   **Purpose**: To ground the Learnings in a structured framework.

## The Condensation Process (The "Loop")

1.  **Trigger**: Periodic job (every X minutes/hours) or event-driven (after N new memories).
2.  **Fetch**: Retrieve recent "Raw Memories" that haven't been processed.
3.  **Cluster**: Use vector similarity to group related memories.
4.  **Synthesize (LLM)**:
    -   Prompt: "Analyze these X memories. Identify any recurring patterns, user preferences, or factual constraints. Output as structured 'Learnings'."
5.  **De-duplicate**: Check new Learnings against existing ones (using Vector Search on the `Learning` collection).
    -   If match: Update existing Learning (increment frequency/confidence, add new evidence).
    -   If new: Create new Learning record.
6.  **Edge Synthesis & Co-occurrence**:
    -   Run `EdgeSynthesizer` to detect pairwise co-occurrences of entities within the same context.
    -   Upsert `Relation` edges with type `CO_OCCURS_WITH`.
    -   Strengthen existing edges using Hebbian reinforcement.
7.  **De-duplicate & Consolidate**:
    -   Use `KnowledgeConsolidator` to merge new facts into existing `Assertions`.
    -   Update confidence and track provenance.

## Cognitive Dynamics (The "Mind")

The system implements a Hebbian-inspired learning model to manage the "vibrancy" of memories.

### 1. Hebbian Reinforcement (LTP)
-   **Trigger**: Every time a `Relation` or `Assertion` is retrieved to answer a query.
-   **Action**: `CognitiveService.hebbian_update(ids)` increments the `access_count` and increases the `strength`.
-   **Logic**: "Cells that fire together, wire together." Frequently used facts become "heavier" in the graph.

### 2. Spreading Activation
-   **Retrieval**: When an entity is mentioned, all related neighbors (via `Relation` edges) are activated.
-   **Weighting**: The `strength` of the edge determines how much activation flows to the neighbor.
-   **Pruning**: Nodes with low activation are culled from the context.

### 3. Activation Decay (LTD)
-   **Trigger**: Periodic maintenance job.
-   **Action**: `CognitiveService.apply_activation_decay()` reduces the `strength` of all facts.
-   **Result**: Unused information eventually fades, preventing the context window from being cluttered by legacy data.

## Retrieval Workflow (The "Filter")

When a new Query comes in:
1.  **Vector Search (Learnings)**: Find top K relevant Learnings.
2.  **Graph Traversal (Ontology)**: Find related concepts.
3.  **Vector Search (Memories)**: Find specific recent details (standard RAG).
4.  **Context Construction**:
    -   System Prompt: "You are helpful..."
    -   **Learnings Context**: "Key insights about this user/project: ..."
    -   **Memory Context**: "Relevant recent events: ..."

## "Pluggable" Retroactive Learning

A specific mode `run_retroactive_learning(project_id)`:
1.  Iterates over ALL existing memories in Qdrant/DB.
2.  Batches them by time or topic.
3.  Runs the Condensation Loop.
4.  Populates the initial set of Learnings and Ontology.
