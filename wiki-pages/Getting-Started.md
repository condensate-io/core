# Getting Started

Welcome to Condensate! This guide will walk you through spinning up your first instance of the Condensate Memory Operating System and integrating it with a simple agent using the Python SDK.

---

## 🚀 Quickstart via Docker Compose

The easiest way to get Condensate running locally is via Docker Compose. This will spin up the Condensate Core API, the Admin Dashboard, Qdrant (for vector storage), and Ollama (for local inference if configured).

### 1. Clone the Repository

```bash
git clone https://github.com/condensate-io/core
cd core
```

### 2. Configure Environment Variables

Copy the example environment file and configure it as needed. For a basic local setup, the defaults in `.env.example` are usually sufficient.

```bash
cp .env.example .env
```

If you plan to use external LLMs (like OpenAI or Anthropic) instead of local inference, be sure to set your API keys in the `.env` file.

### 3. Start the Services

```bash
docker compose up -d
```

This will start:
- **Core API**: `http://localhost:8000`
- **Admin Dashboard**: `http://localhost:3010`
- **Qdrant**: `http://localhost:6333`

---

## 🔑 Creating Projects and API Keys

Before you can ingest memory, you need to create a Project and an associated API Key. Condensate uses a strict multi-tenant model where all data is scoped to a specific project.

You can do this via the Admin Dashboard (`http://localhost:3010`) or via the admin REST endpoints.

```bash
curl -X POST http://localhost:8000/api/admin/projects \
  -H "Authorization: Basic YWRtaW46YWRtaW4=" \
  -H "Content-Type: application/json" \
  -d '{"name": "My First Agent Swarm", "api_key_name": "default-key"}'
```

This will return a JSON response containing your new `project_id` and `api_key`. Save the `api_key` securely!

---

## 🧠 First Ingestion (Python SDK)

Now that you have a project and an API key, let's store your first episodic memory using the [[SDKs-and-Integration|Python SDK]].

First, install the SDK:

```bash
pip install condensate
```

Then, run the following Python script:

```python
from condensate import CondensateClient

# Initialize the client with your core URL and the API key you generated
client = CondensateClient("http://localhost:8000", api_key="sk-your-key")

# Store an episodic memory
response = client.store_memory(
    content="The user loves building autonomous agents and prefers Python.",
    type="episodic",
    source="chat"
)

print(f"Stored memory: {response}")
```

Behind the scenes, Condensate will route this memory through its L3 Condenser pipeline, run Named Entity Recognition (NER), canonicalize entities, and weave it into your project's cryptographic Merkle-DAG.

---

## 🔍 Retrieving Memory

Once memories are stored and condensed, your agents can query the memory graph.

```python
# Retrieve context for an agent
context = client.retrieve(
    query="What languages does the user prefer?",
    strategy="hybrid" # Uses both vector similarity and graph traversal
)

print(context)
```

Condensate returns verified, logically consistent context by traversing the causal graph, completely avoiding the [[The-Problem#contradiction-blindness|Contradiction Blindness]] typical of standard vector databases.

---

**Next Steps**: 
- Read about the [[Architecture]] to understand how the memory is structured.
- Learn how the [[Synapse-Engine]] automatically surfaces relevant memories over time.
