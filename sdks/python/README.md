# Condensate Python SDK

Official Python client for [Condensate](https://condensate.io) — the open-source Agent Memory System.

[![PyPI](https://img.shields.io/pypi/v/condensate)](https://pypi.org/project/condensate/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](../../LICENSE)

## Installation

```bash
pip install condensate
```

Requires Python 3.9+.

## Quick Start

```python
from condensate import CondensateClient

client = CondensateClient(
    base_url="http://localhost:8000",
    api_key="sk-your-api-key"
)

# Store a memory
client.store_memory(
    content="The team decided to use PostgreSQL for the primary store.",
    type="episodic",
    metadata={"source": "meeting", "project": "infra-v2"}
)

# Retrieve relevant memories
result = client.retrieve("What database did we choose?")
print(result["answer"])
print(result["sources"])   # list of episodic item IDs
print(result["strategy"])  # "recall" | "research" | "meta"
```

## Configuration

### Environment Variables

Set these before initialising the client, or pass them directly:

| Variable | Description | Default |
|---|---|---|
| `CONDENSATE_URL` | Base URL of your Condensate server | `http://localhost:8000` |
| `CONDENSATE_API_KEY` | API key (create one in the admin dashboard) | — |

```python
import os
from condensate import CondensateClient

client = CondensateClient(
    base_url=os.environ["CONDENSATE_URL"],
    api_key=os.environ["CONDENSATE_API_KEY"]
)
```

### Connecting to a Remote Server

```python
client = CondensateClient(
    base_url="https://memory.yourcompany.com",
    api_key="sk-prod-xxxx"
)
```

## API Reference

### `store_memory(content, type, metadata)`

Stores a raw episodic item and runs the full condensation pipeline (NER → entity extraction → assertion creation).

```python
client.store_memory(
    content="Alice approved the Q3 roadmap.",
    type="episodic",          # episodic | note | event
    metadata={
        "source": "slack",
        "channel": "#product"
    }
)
```

### `retrieve(query)`

Routes the query through the Memory Router (vector search + optional graph traversal) and returns a synthesised answer.

```python
result = client.retrieve("What did Alice approve?")
# {
#   "answer": "Alice approved the Q3 roadmap.",
#   "sources": ["<uuid>", ...],
#   "strategy": "recall"
# }
```

### `add_item(item)` *(low-level)*

Directly posts an `EpisodicItemCreate` payload to the v1 API.

```python
from condensate import EpisodicItem
import uuid

client.add_item(EpisodicItem(
    project_id=str(uuid.uuid4()),
    source="api",
    text="User prefers dark mode."
))
```

## CLI

The package ships a `condensate` CLI:

```bash
# Store a memory from stdin
echo "Deploy to prod on Friday" | condensate store --type episodic

# Retrieve
condensate retrieve "When are we deploying?"
```

Set `CONDENSATE_URL` and `CONDENSATE_API_KEY` in your shell before using the CLI.

## Self-Hosting

See the [main README](../../README.md#getting-started) for Docker Compose setup. The server must be running before the SDK can connect.

## Development

```bash
cd sdks/python
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```
