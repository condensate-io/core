# Learning Graph Model

**Status**: Draft
**Version**: 0.1

## Overview

The Learning Graph is the "Long Term Memory" of the agent. It is not just a vector store, but a structured graph of concepts (Ontology) populated by specific instances (Learnings).

## Layers

1.  **The Conceptual Layer (Ontology)**
    -   Universal concepts (e.g., "Database", "Python").
    -   Domain-specific concepts (e.g., "Project X").
    -   These are the immutable "anchors" of the graph.

2.  **The Instance Layer (Assertions)**
    -   Specific instantiations or observations.
    -   E.g., "Project X uses Postgres" is an Assertion that connects the node "Project X" to "Postgres" via a "USES" edge.

## Edge Types

-   `IS_A`: Hierarchical (Postgres IS_A Database).
-   `HAS_PROPERTY`: Attribute (User HAS_PROPERTY "verbose").
-   `CO_OCCURS_WITH`: Synthesized association (Entity A and B appear together frequently).
-   `RELATED_TO`: General association.
-   `CAUSES`: Causal link (A CAUSES B).

## Graph Traversal & Cognitive Gravity

When building context for an LLM:
1.  **Identify Key Entities** in the user's prompt (NER).
2.  **Activate Nodes** in the graph corresponding to these entities.
3.  **Spread Activation**: Activation flows to connected nodes. The amount of activation is proportional to the edge `strength` (Hebbian weight).
4.  **Cognitive Gravity**: Highly reinforced nodes "pull" related context more strongly.
5.  **Retrieve Learnings**: Assertions attached to these active nodes are injected into context.
