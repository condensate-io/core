# Condensate: Agent Memory System

> **Standardizing the "Brain" of AI Agents.**

Condensate is an open-source Memory Condensation OS that gives AI agents structured, deterministic, and verifiable long-term memory. It replaces the "bag of text" RAG approach with a rigorous ontology of **Events**, **Learnings**, and **Policies**, enforcing **Traffic Control** (No-LLM paths) and **Cognitive Provenance** (Proof Envelopes).

## Installation

**Python**
```bash
pip install condensate
```

**TypeScript / Node.js**
```bash
npm install @condensate/sdk
```

**Claude / Cursor / Windsurf (MCP)**
```bash
npx -y @condensate/core
```

**Rust**
```bash
cargo add condensate
```

**Go**
```bash
go get github.com/condensate/condensate-go-sdk
```

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Python 3.11+

### 1. Clone and Configure

```bash
git clone https://github.com/condensate-io/core
cd core
cp .env.example .env
# Edit .env with your settings (see Environment Variables below)
```

### 2. Start the Stack

```bash
./start.sh
```

This starts:
- **Condensate Core API** on `http://localhost:8000`
- **Admin Dashboard** on `http://localhost:3010`
- **Qdrant** (vector store) on `http://localhost:6333`
- **Ollama** (local LLM) on `http://localhost:11434`

### 3. Create an API Key

Open [http://localhost:3010](http://localhost:3010) → **API Keys** → **Create Key**. Copy the `sk-...` value.

### 4. Connect an SDK

```python
from condensate import CondensateClient

client = CondensateClient("http://localhost:8000", "sk-your-key")
client.store_memory(content="User prefers dark mode.", type="episodic")
result = client.retrieve("What are the user's preferences?")
print(result["answer"])
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

### Core Services

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://condensate:password@db:5432/condensate_db` |
| `QDRANT_HOST` | Qdrant hostname (used in docker-compose) | `qdrant` |
| `QDRANT_PORT` | Qdrant port | `6333` |
| `QDRANT_URL` | Full Qdrant URL — overrides HOST+PORT when set | `http://{QDRANT_HOST}:{QDRANT_PORT}` |
| `QDRANT_API_KEY` | Qdrant API key (required for Qdrant Cloud) | — |

### LLM Provider

| Variable | Description | Default |
|---|---|---|
| `LLM_ENABLED` | Enable LLM-based extraction pipeline | `false` |
| `LLM_BASE_URL` | OpenAI-compatible base URL | `http://ollama:11434/v1` |
| `LLM_API_KEY` | LLM provider API key | `ollama` |
| `LLM_MODEL` | Model name for extraction | `phi3` |

### NER Model

| Variable | Description | Default |
|---|---|---|
| `HF_TOKEN` | Hugging Face token — enables authenticated downloads and higher rate limits for the ModernBERT NER model. Strongly recommended to avoid cold-start failures. | — |

### Security

| Variable | Description | Default |
|---|---|---|
| `CONDENSATE_SECRET` | HMAC secret for signing Proof Envelopes | `changeme_in_production` |
| `ADMIN_USERNAME` | Admin dashboard username | `admin` |
| `ADMIN_PASSWORD` | Admin dashboard password | `admin` |

### Memory Pipeline

| Variable | Description | Default |
|---|---|---|
| `REVIEW_MODE` | Assertion review mode: `manual` (HITL queue) or `auto` | `manual` |
| `INSTRUCTION_BLOCK_THRESHOLD` | Guardrail threshold for instruction injection (0.0–1.0) | `0.5` |
| `SAFETY_BLOCK_THRESHOLD` | Guardrail threshold for safety violations (0.0–1.0) | `0.7` |

### Ingestion

| Variable | Description | Default |
|---|---|---|
| `INGEST_WORKERS` | Parallel worker threads for `ingest_codebase.py` | `8` |
| `UPLOAD_DIR` | Directory for file uploads (relative to app root) | `uploads` |

### SDK / Client

| Variable | Description | Default |
|---|---|---|
| `CONDENSATE_URL` | Server URL used by the Python SDK CLI | `http://localhost:8000` |
| `CONDENSATE_API_KEY` | API key used by the Python SDK CLI | — |

### Data Migration (optional)

| Variable | Description | Default |
|---|---|---|
| `LOCALMEMCP_PATH` | Path to LocalMem data directory for bootstrap import | `/app/localmemcp_data` |
| `OLD_QDRANT_HOST` | Old Qdrant host for data migration | `host.docker.internal` |
| `OLD_QDRANT_PORT` | Old Qdrant port for data migration | `6333` |

### Using a Cloud LLM (OpenAI)

```env
LLM_ENABLED=true
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-openai-xxxx
LLM_MODEL=gpt-4o-mini
```

### Using a Local LLM (Ollama)

```env
LLM_ENABLED=true
LLM_BASE_URL=http://ollama:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=phi3
```

## SDKs

| SDK | Package | Docs |
|---|---|---|
| Python | [`condensate`](https://pypi.org/project/condensate/) | [sdks/python](sdks/python/README.md) |
| TypeScript | [`@condensate/sdk`](https://www.npmjs.com/package/@condensate/sdk) | [sdks/ts](sdks/ts/README.md) |
| MCP Bridge | [`@condensate/core`](https://www.npmjs.com/package/@condensate/core) | [sdks/mcp-bridge](sdks/mcp-bridge/README.md) |
| Rust | [`condensate`](https://crates.io/crates/condensate) | [sdks/rust](sdks/rust/README.md) |
| Go | [`condensate-go-sdk`](https://pkg.go.dev/github.com/condensate/condensate-go-sdk) | [sdks/go](sdks/go/README.md) |

## Architecture

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
   [Knowledge Graph] ─── Entities, Assertions, Relations (Postgres)
        │
        ▼
   [Memory Router]  ──── Vector search + Graph traversal + Hebbian updates
        │
        ▼
   [MCP / API]      ──── Agents, SDKs, Admin Dashboard
```

## Releasing

Releases are triggered by pushing a version tag:

```bash
git tag v1.2.3
git push origin v1.2.3
```

This triggers the GitHub Actions release workflow which:
1. Builds Rust binaries for Linux, macOS (x64 + arm64), and Windows
2. Publishes `condensate` to [PyPI](https://pypi.org/project/condensate/)
3. Publishes `@condensate/sdk` and `@condensate/core` to [npm](https://www.npmjs.com/)
4. Publishes `condensate` to [crates.io](https://crates.io/crates/condensate)
5. Creates a GitHub Release with binary attachments

### Required GitHub Secrets

| Secret | Description |
|---|---|
| `NPM_TOKEN` | npm Automation token (`npm token create --type=automation`) |
| `PYPI_API_TOKEN` | PyPI API token (starts with `pypi-`) |
| `CARGO_REGISTRY_TOKEN` | crates.io API token |
| `GITHUB_TOKEN` | Injected automatically by GitHub Actions |

## Running Tests

```bash
./run_tests.sh
```

## Documentation Index

### 🏛️ Governance & Standards
- [Governance](GOVERNANCE.md)
- [Contributing](CONTRIBUTING.md)
- [Versioning](VERSIONING.md)
- [Security](SECURITY.md)

### 📜 Core Specifications
- [Memory Schema](spec/memory-schema.md)
- [Cognitive Provenance](spec/cognitive-provenance.md)
- [Capability Contract](spec/capability-contract.md)
- [Replay Semantics](spec/replay-semantics.md)

### 🏗️ Reference Architecture
- [Agent Operating Model](reference-architecture/agent-operating-model.mermaid)
- [Cognitive Provenance Flow](reference-architecture/cognitive-provenance-flow.mermaid)
- [Threat Model](reference-architecture/threat-model.md)

### 📝 RFCs
- [0001: Strict Memory Schema](rfcs/0001-memory-schema.md)
- [0002: Proof Envelope](rfcs/0002-proof-envelope.md)
- [0003: Taint Model](rfcs/0003-taint-model.md)

## Ecosystem

Condensate works with any OpenAI-compatible LLM provider and any MCP-compatible agent:

- **Model Providers**: OpenAI, Anthropic, Azure OpenAI, Google Gemini, Mistral
- **Local Inference**: Ollama, LM Studio, LocalAI
- **Agent Frameworks**: LangChain, LlamaIndex, AutoGen, CrewAI
- **Agent Hosts**: Claude Desktop, Cursor, Windsurf, Codeium

## License

Apache 2.0 — see [LICENSE](LICENSE).
