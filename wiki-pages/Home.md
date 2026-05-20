# ⚡ Condensate — The Memory Operating System for AI Agents

> **Current AI Memory is Built for Search. Condensate is Built for Cognition.**

**Condensate** is an open-source Memory Operating System — the canonical, cross-vendor memory substrate for autonomous AI agents. It replaces brittle RAG pipelines and flat vector lookups with a rigorous ontology of **Events**, **Learnings**, and **Policies**, enforced by cryptographic provenance and active learning.

Where vector databases approximate similarity in a high-dimensional space, Condensate traverses a **verifiable, multi-agent causal graph**. Every fact has a lineage. Every decision has a proof. Every agent shares a single semantic ground truth.

---

## 🧭 Quick Navigation

| Page | Description |
|------|-------------|
| [[The Problem]] | Why current AI memory architectures fail — and what Condensate fixes |
| [[Architecture]] | Merkle-DAGs, CRDTs, the Condenser pipeline, and Proof Envelopes |
| [[Synapse Engine]] | Hebbian learning, memory consolidation, and adaptive decay |
| [[SDKs and Integration]] | Python, TypeScript, Rust, Go SDKs and MCP Bridge |
| [[Getting Started]] | Docker quickstart, environment setup, and first ingestion |
| [[Security and Threat Model]] | Provenance chains, guardrails, multi-tenant isolation |
| [[FAQ]] | Common questions about Condensate |

---

## 🔍 What Condensate Does

### The Problem

AI agents today are forced to build long-term memory on top of systems designed for document search. Vector databases return contradictory chunks. Proprietary memory APIs trap cognitive data in walled gardens. Last-Write-Wins concurrency destroys nuanced multi-agent state.

**The result:** agents that hallucinate, forget, and can't explain why they believe what they believe.

### The Solution

Condensate introduces a fundamentally different architecture:

- **Structured Memory Ontology** — Raw events are condensed into typed Entities, Assertions, Relations, Events, Learnings, and Policies — not just embedded as text blobs.
- **Cryptographic Provenance** — Every assertion is wrapped in a Proof Envelope with HMAC signatures and input hashes. You can trace any belief back to the observations that justified it.
- **Active Learning** — The [[Synapse Engine]] creates weighted semantic connections between memories, strengthens them through retrieval, and consolidates dense clusters into higher-order knowledge.
- **Multi-Agent Concurrency** — CRDT-based conflict resolution allows multiple agents to mutate memory simultaneously without coordination or data loss.
- **Vendor Independence** — Works with any OpenAI-compatible LLM provider. Your cognitive graph is never trapped.

---

## 🏗️ Architecture at a Glance

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

→ Deep dive: [[Architecture]]

---

## 🚀 Get Started in 60 Seconds

```bash
git clone https://github.com/condensate-io/core
cd core
cp .env.example .env
docker compose up
```

Then connect with the Python SDK:

```python
from condensate import CondensateClient

client = CondensateClient("http://localhost:8000", "sk-your-key")
client.store_memory(content="User prefers dark mode.", type="episodic")
result = client.retrieve("What are the user's preferences?")
print(result["answer"])
```

→ Full walkthrough: [[Getting Started]]

---

## 📦 SDKs

| SDK | Install | Docs |
|-----|---------|------|
| Python | `pip install condensate` | [sdks/python](https://github.com/condensate-io/core/tree/main/sdks/python) |
| TypeScript | `npm install @condensate/sdk` | [sdks/ts](https://github.com/condensate-io/core/tree/main/sdks/ts) |
| MCP Bridge | `npx -y @condensate/core` | [sdks/mcp-bridge](https://github.com/condensate-io/core/tree/main/sdks/mcp-bridge) |
| Rust | `cargo add condensate` | [sdks/rust](https://github.com/condensate-io/core/tree/main/sdks/rust) |
| Go | `go get github.com/condensate/condensate-go-sdk` | [sdks/go](https://github.com/condensate-io/core/tree/main/sdks/go) |

→ Full SDK reference: [[SDKs and Integration]]

---

## 🌐 Ecosystem Compatibility

Condensate works with any OpenAI-compatible LLM provider and any MCP-compatible agent:

- **Model Providers:** OpenAI, Anthropic, Azure OpenAI, Google Gemini, Mistral
- **Local Inference:** Ollama, LM Studio, LocalAI
- **Agent Frameworks:** LangChain, LlamaIndex, AutoGen, CrewAI
- **Agent Hosts:** Claude Desktop, Cursor, Windsurf, Codeium

---

## 🔗 Links

| | |
|---|---|
| 🌐 **Website** | [https://www.condensate.io](https://www.condensate.io) |
| 💻 **GitHub** | [https://github.com/condensate-io/core](https://github.com/condensate-io/core) |
| 💼 **LinkedIn** | [https://www.linkedin.com/company/condensate-io/](https://www.linkedin.com/company/condensate-io/) |
| 📍 **Location** | Melbourne, Victoria, Australia |
| 📄 **License** | Apache 2.0 |

---

## 📖 Further Reading

- [Whitepaper](https://www.condensate.io) — The full technical whitepaper on the Condensate data protocol
- [Contributing](https://github.com/condensate-io/core/blob/main/CONTRIBUTING.md) — How to contribute to Condensate
- [Security Policy](https://github.com/condensate-io/core/blob/main/SECURITY.md) — Responsible disclosure and supported versions
- [Governance](https://github.com/condensate-io/core/blob/main/GOVERNANCE.md) — Project governance model
