<div align="center">

# 🧠 condensate

### The Canonical Memory Substrate for Autonomous AI

**Current AI Memory is Built for Search. Condensate is Built for Cognition.**

[![Website](https://img.shields.io/badge/condensate.io-000000?style=for-the-badge&logo=google-chrome&logoColor=white)](https://www.condensate.io)
[![GitHub](https://img.shields.io/badge/condensate--io/core-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/condensate-io/core)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/company/condensate-io/)
[![License](https://img.shields.io/badge/Apache_2.0-D22128?style=for-the-badge&logo=apache&logoColor=white)](https://github.com/condensate-io/core/blob/main/LICENSE)

[![PyPI](https://img.shields.io/pypi/v/condensate?style=flat-square&logo=python&logoColor=white&label=python)](https://pypi.org/project/condensate/)
[![npm](https://img.shields.io/npm/v/@condensate/sdk?style=flat-square&logo=npm&logoColor=white&label=typescript)](https://www.npmjs.com/package/@condensate/sdk)
[![crates.io](https://img.shields.io/crates/v/condensate?style=flat-square&logo=rust&logoColor=white&label=rust)](https://crates.io/crates/condensate)
[![npm MCP](https://img.shields.io/npm/v/@condensate/core?style=flat-square&logo=npm&logoColor=white&label=mcp)](https://www.npmjs.com/package/@condensate/core)

---

*Open-source Memory Condensation Operating System — the cross-vendor memory substrate for AI agent swarms.*

</div>

---

## 💡 The Problem

AI agents today run on **broken memory**. Vector databases approximate similarity. Chat logs lose causality. Every vendor locks you into a proprietary silo. When agents collaborate, memories collide — and the last write wins.

| Failure Mode | Root Cause | What Gets Lost |
|:---|:---|:---|
| 🔴 **Contradiction Blindness** | Vector DBs return "similar" — not "true" | Factual consistency |
| 🔴 **Lost Causality** | Flat text has no causal structure | *Why* something was learned |
| 🔴 **Vendor Lock-In** | Proprietary memory APIs | Portability & data sovereignty |
| 🔴 **Concurrency Failures** | Last-Write-Wins across agents | Deterministic multi-agent merge |

---

## ⚡ How Condensate Fixes It

Condensate shifts AI memory from *"approximating similarity in a vector space"* to *"traversing a verifiable, multi-agent causal graph."*

| Capability | Technology | Why It Matters |
|:---|:---|:---|
| 🔗 **Verifiable Provenance** | Cryptographically-Signed Merkle-DAGs | Every memory has a tamper-proof chain of origin |
| 🤝 **Deterministic Multi-Agent Merge** | CRDTs (Conflict-Free Replicated Data Types) | N agents, zero conflicts, guaranteed convergence |
| 🧬 **Active Learning** | Synapse Engine — Hebbian Learning | Neurons that fire together, wire together |
| 🌐 **Cross-Vendor Interop** | Vendor-agnostic substrate | OpenAI + Anthropic + local model = one shared brain |
| 🏠 **Data Sovereignty** | Local-first, self-hosted | Your data never leaves your infrastructure |

---

## 🚀 Get Started in 60 Seconds

```bash
git clone https://github.com/condensate-io/core && cd core
cp .env.example .env
./start.sh
```

> **That's it.** Core API on `:8000` · Admin Dashboard on `:3010` · Qdrant on `:6333` · Ollama on `:11434`

Then connect from any SDK:

```python
from condensate import CondensateClient

client = CondensateClient("http://localhost:8000", "sk-your-key")
client.store_memory(content="User prefers dark mode.", type="episodic")
result = client.retrieve("What are the user's preferences?")
```

---

## 📦 SDKs

Install the SDK for your stack — or connect any MCP-compatible agent:

```bash
pip install condensate                    # Python
npm install @condensate/sdk               # TypeScript
cargo add condensate                      # Rust
go get github.com/condensate/condensate-go-sdk  # Go
npx -y @condensate/core                   # MCP Bridge (Claude, Cursor, Windsurf)
```

---

## 🏗️ Architecture at a Glance

```
Raw Input (Chat / Docs / API)
        │
        ▼
   Ingress Agent ────── episodic memory + vector embedding
        │
        ▼
   Condenser ────────── NER → extraction → canonicalization → consolidation
        │
        ▼
   Synapse Engine ───── multi-signal scoring → Hebbian learning → clustering
        │
        ▼
   Knowledge Graph ──── entities, assertions, relations (Postgres)
        │
        ▼
   Memory Router ────── vector search + graph traversal + Hebbian updates
        │
        ▼
   MCP / API ────────── agents, SDKs, admin dashboard
```

---

## 🌍 Ecosystem

Condensate is **vendor-agnostic by design**. It works with:

**Model Providers** — OpenAI · Anthropic · Azure OpenAI · Google Gemini · Mistral
**Local Inference** — Ollama · LM Studio · LocalAI
**Agent Frameworks** — LangChain · LlamaIndex · AutoGen · CrewAI
**Agent Hosts** — Claude Desktop · Cursor · Windsurf · Codeium

---

## 🤝 Get Involved

<div align="center">

| | |
|:---:|:---:|
| 📖 [**Documentation**](https://github.com/condensate-io/core#readme) | 🐛 [**Issues**](https://github.com/condensate-io/core/issues) |
| 📝 [**Contributing Guide**](https://github.com/condensate-io/core/blob/main/CONTRIBUTING.md) | 💬 [**Discussions**](https://github.com/condensate-io/core/discussions) |
| 🔐 [**Security Policy**](https://github.com/condensate-io/core/blob/main/SECURITY.md) | ⭐ [**Star the repo**](https://github.com/condensate-io/core) |

</div>

---

<div align="center">

**Standardizing the brain of AI agents.**

🇦🇺 Built in Melbourne, Australia · Open source · Apache 2.0

[![Star History](https://img.shields.io/github/stars/condensate-io/core?style=social)](https://github.com/condensate-io/core)

</div>
