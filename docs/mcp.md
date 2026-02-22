# Model Context Protocol (MCP) Server

The Condensate system includes a high-performance **MCP Server** built on top of FastAPI. This allows AI models (like Claude, GPT-4, or custom agents) to directly interact with the memory system using standard tool-calling patterns.

## Endpoint
The MCP root is hosted at: `http://localhost:8000/mcp`

---

## Available Tools

### 1. `store_memory`
Directly injects a raw episodic memory into the current project scope.

**Input Schema:**
- `content` (string, required): The raw text to store.
- `type` (string, enum): `episodic` (default) or `semantic`.

**Example Usage:**
```json
{
  "name": "store_memory",
  "arguments": {
    "content": "User mentioned they prefer Python for backend tasks.",
    "type": "episodic"
  }
}
```

### 2. `add_data_source`
Configures a new automated ingestion source.

**Input Schema:**
- `name` (string, required): Human-readable name for the source.
- `source_type` (string, required): `url`, `file`, or `api`.
- `configuration` (object): Source-specific settings (e.g., URL endpoint, file path).

### 3. `trigger_data_source`
Manually starts a background ingestion job for an existing source.

**Input Schema:**
- `source_id` (string, required): The UUID of the data source to trigger.

---

## Integration Guide

### API Authentication
The MCP server requires the same `Authorization: Bearer <sk-key>` header as the standard API. Ensure your agent has a valid API key from the Admin Dashboard.

### Schema Adherence
The server strictly enforces Pydantic-based schema validation. If a tool call fails, check the `MCPServer` logs in the backend container for detailed validation errors.

### Workflow Example
1. Agent identifies a piece of long-term information in a chat.
2. Agent calls `store_memory` via the MCP bridge.
3. The Condensate **Ingress Agent** hashes the content, generates embeddings, and saves it to the Episodic Store.
4. The background **Condenser** asynchronously distills this into a canonical assertion.
