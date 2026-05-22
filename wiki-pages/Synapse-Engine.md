# The Synapse Engine

At the heart of Condensate's [[Architecture]] is the **Synapse Engine** — a system that moves AI memory from passive storage to active, dynamic cognition.

Traditional vector databases act like filing cabinets: they only return what you explicitly ask for based on semantic similarity. The Synapse Engine behaves more like a biological brain, dynamically strengthening connections between concepts over time.

---

## 🧠 What are Synapses?

In Condensate, the knowledge graph is composed of Entities (nodes) and Relations (edges). A **Synapse** is a specialized, weighted semantic connection overlaying this graph.

Rather than relying purely on static metadata, synapses represent the *strength and relevance* of the relationship between two entities based on how frequently they are accessed together.

---

## ⚡ Hebbian Learning

The Synapse Engine operates on the principle of **Hebbian Learning**: *"Neurons that fire together, wire together."*

When an agent retrieves context that involves multiple entities (e.g., querying about a "User" and a specific "Project"), the Synapse Engine observes this co-activation. It automatically increases the synaptic weight between those entities. 

Over time, entities that are frequently used together form dense "cognitive communities." This allows Condensate to preemptively surface highly relevant contextual information that a simple vector search would miss.

---

## 🔄 Memory Consolidation Cycles

The Synapse Engine runs continuous background processes (similar to biological sleep cycles) to maintain the health of the memory graph:

1. **Clustering**: The engine identifies tightly bound entity communities and physically groups them for faster retrieval.
2. **Canonicalization**: Redundant or highly similar entities that share identical synaptic pathways are merged (e.g., merging "AWS" and "Amazon Web Services").
3. **Graph Compaction**: Overly complex graph structures are simplified to reduce token payload size during LLM context injection.

---

## 📉 Temporal Decay

Not all memories are equally important forever. The Synapse Engine implements **Temporal Decay**.

Synaptic weights slowly decay over time if they are not activated by agent queries or new episodic inputs. This prevents the knowledge graph from becoming cluttered with stale or obsolete relationships. However, core memories with extremely high weights (or those explicitly pinned by the user) resist this decay.

---

## 🧩 Integration with the Condenser Pipeline

The Synapse Engine works hand-in-hand with Condensate's L3 Condenser pipeline:

1. **Ingestion**: Raw episodic memory arrives via the [[SDKs-and-Integration|SDKs]].
2. **Condensation**: The deterministic condenser extracts entities and assertions.
3. **Synaptic Wiring**: The Synapse Engine evaluates the new entities against the existing graph, forging new synapses and updating the weights of existing ones.
4. **Retrieval**: When an agent queries the memory, the Memory Router uses the synaptic weights to traverse the graph and return the most cognitively relevant context.
