# Getting Started with Condensate

Welcome to Condensate, the "Memory Condensate OS" for AI agents. This guide will help you set up the system and run your first memory ingestion.

## 1. Prerequisites
- **Docker & Docker Compose**
- **Ollama** (for local LLM support) or an **OpenAI API Key**.

## 2. Installation

Clone the repository and start the stack:
```bash
git clone https://github.com/condenstate-io/core
cd core
docker-compose up -d
```

The system will be available at:
- **Admin Dashboard**: `http://localhost:8000`
- **API**: `http://localhost:8000/api/v1`
- **MCP**: `http://localhost:8000/mcp`

## 3. Initial Configuration

1. Open the **Admin Dashboard**.
2. Go to the **Settings** (LLM Configuration) tab.
3. Configure your endpoint:
   - **Local**: Base URL `http://localhost:11434/v1`, Model `phi3`.
   - **Cloud**: Base URL `https://api.openai.com/v1`, Model `gpt-4-turbo`, and your API Key.
4. Go to the **API Keys** tab and create a new key for your project.

## 4. Ingesting Data

Condensate provides multiple ingestion methods to fit your workflow.

### Via CLI (Quickest)

Both Python and Rust provide a `condensate` command-line tool:

```bash
# Set your endpoint and API key
export CONDENSATE_URL=http://localhost:8000
export CONDENSATE_API_KEY=<YOUR_API_KEY>

# Ingest a memory
condensate ingest "Project X is migrating to Postgres v15"

# Retrieve memories
condensate recall "What database is Project X using?"
```

**Installation:**
- Python: `pip install condensate`
- Rust: `cargo install condensate`

---

### Via Python SDK

```python
from condensate import CondensateClient

client = CondensateClient(
    base_url="http://localhost:8000",
    api_key="<YOUR_API_KEY>"
)

# Ingest a memory
item_id = client.add_item(
    text="Project X is migrating to Postgres v15",
    source="api"
)
print(f"Ingested: {item_id}")

# Retrieve memories
result = client.retrieve("What database is Project X using?")
print(result["answer"])
```

**Installation:** `pip install condensate`

---

### Via Rust SDK

```rust
use condensate::{CondensateClient, EpisodicItem};

fn main() {
    let client = CondensateClient::new(
        "http://localhost:8000",
        "<YOUR_API_KEY>"
    );

    // Ingest a memory
    let item_id = client.add_item(
        "Project X is migrating to Postgres v15",
        "api"
    ).unwrap();
    println!("Ingested: {}", item_id);

    // Retrieve memories
    let result = client.retrieve("What database is Project X using?").unwrap();
    println!("Answer: {:?}", result.answer);
}
```

**Installation:** Add to `Cargo.toml`:
```toml
[dependencies]
condensate = "0.1"
```

---

### Via Node/TypeScript SDK

```typescript
import { CondensatesClient } from '@condensate/sdk';

const client = new CondensatesClient(
    'http://localhost:8000',
    '<YOUR_API_KEY>'
);

// Ingest a memory
const item = await client.addItem({
    project_id: '<YOUR_PROJECT_ID>',
    source: 'api',
    text: 'Project X is migrating to Postgres v15'
});
console.log(`Ingested: ${item.id}`);
```

**Installation:** `npm install @condensate/sdk`

---

### Via MCP (Model Context Protocol)

If you're using an MCP-compatible AI client (e.g., Claude Desktop), install the bridge:

```bash
npm install -g @condensate/core
```

Then configure your MCP client to use `condensate-mcp` as a server. The AI will automatically have access to `store_memory` and `trigger_data_source` tools.

---

### Via REST API (curl)

```bash
curl -X POST http://localhost:8000/api/v1/episodic \
     -H "Authorization: Bearer <YOUR_API_KEY>" \
     -H "Content-Type: application/json" \
     -d '{
       "source": "api",
       "text": "Project X is migrating to Postgres v15"
     }'
```

## 5. Visualizing the Graph
Once ingested, wait ~30 seconds for the **Condenser** to process the memory. Navigate to the **Ontology Graph** view in the dashboard to see "Project X" and "Postgres v15" appear as canonical nodes with a synthesized relationship.
