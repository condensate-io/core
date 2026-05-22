# Frequently Asked Questions (FAQ)

---

### Is Condensate a vector database?

**No — it's a Memory Operating System.** 
While Condensate uses a vector database (Qdrant) under the hood for semantic search, that is only one part of the system. Condensate layers a deterministic condenser, a cryptographically signed Merkle-DAG for verifiable causality, and a dynamic [[Synapse-Engine]] over the raw vectors. It is a complete cognitive infrastructure layer for AI agents, not just a storage engine.

---

### Does Condensate replace RAG (Retrieval-Augmented Generation)?

**No, it supercharges it.**
Traditional RAG relies on chunking documents and hoping vector similarity returns the right facts. Condensate complements RAG by providing structured, verified, and causally-linked memory. You can use standard RAG for large static document retrieval, and Condensate for dynamic agent state, changing facts, and multi-agent collaboration.

---

### What LLMs does Condensate support?

**Any LLM you want.**
Condensate is vendor-agnostic by design. The L2 enrichment pipeline can be configured to use OpenAI, Anthropic, Google Gemini, or entirely local models via Ollama. This ensures you avoid [[The-Problem#vendor-lock-in|Vendor Lock-In]] and maintain full data sovereignty.

---

### Can multiple agents share the same memory?

**Yes — that's the core design.**
Condensate utilizes Conflict-Free Replicated Data Types (CRDTs) to allow multiple agents (even running on different machines or using different LLM providers) to read and write to the same memory graph concurrently. It mathematically guarantees that memories will merge deterministically without Last-Write-Wins collisions.

---

### Is Condensate production ready?

Condensate is under **active development** and is used internally for production workloads. However, the APIs are currently classified as *Experimental* (see our [[Architecture]] and versioning docs). Expect rapid iteration and breaking changes in the `0.x` release series as we stabilize the core protocols.

---

### How do I connect my agent?

Check out the [[Getting-Started]] guide and the [[SDKs-and-Integration]] page. We provide native SDKs for Python, TypeScript, Rust, and Go, as well as an MCP (Model Context Protocol) Bridge for seamless integration with tools like Claude Desktop and Cursor.
