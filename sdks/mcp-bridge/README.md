# @condensate/core — MCP Bridge

Expose your [Condensate](https://condensate.io) memory server as a **Model Context Protocol (MCP)** server. Lets Claude, Cursor, Windsurf, and any MCP-compatible agent use Condensate as persistent memory — with a single `npx` command.

[![npm](https://img.shields.io/npm/v/@condensate/core)](https://www.npmjs.com/package/@condensate/core)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](../../LICENSE)

## Quick Start (Claude Desktop)

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "condensate": {
      "command": "npx",
      "args": ["-y", "@condensate/core"],
      "env": {
        "CONDENSATE_URL": "http://localhost:8000",
        "CONDENSATE_API_KEY": "sk-your-api-key"
      }
    }
  }
}
```

Restart Claude Desktop. The `add_memory` and `retrieve_memory` tools will appear automatically.

## Quick Start (Cursor)

Add to `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "condensate": {
      "command": "npx",
      "args": ["-y", "@condensate/core"],
      "env": {
        "CONDENSATE_URL": "http://localhost:8000",
        "CONDENSATE_API_KEY": "sk-your-api-key"
      }
    }
  }
}
```

## Quick Start (Windsurf / Codeium)

Add to your Windsurf MCP settings:

```json
{
  "condensate": {
    "command": "npx",
    "args": ["-y", "@condensate/core"],
    "env": {
      "CONDENSATE_URL": "http://localhost:8000",
      "CONDENSATE_API_KEY": "sk-your-api-key"
    }
  }
}
```

## Environment Variables

| Variable | Description | Required | Default |
|---|---|---|---|
| `CONDENSATE_URL` | Base URL of your Condensate server | No | `http://localhost:8000` |
| `CONDENSATE_API_KEY` | API key from the admin dashboard | Yes (if auth enabled) | — |

## Available MCP Tools

Once connected, the following tools are exposed to your agent:

### `add_memory`

Store a raw memory item (observation, chat log, decision).

| Parameter | Type | Required | Description |
|---|---|---|---|
| `text` | string | ✅ | The memory content to store |
| `source` | string | No | Source label (e.g. `"user"`, `"tool"`) |
| `project_id` | string | No | Project UUID (uses default if omitted) |

### `retrieve_memory`

Retrieve relevant knowledge from Condensate using semantic search + graph traversal.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `query` | string | ✅ | Natural language question |

## Getting Your API Key

1. Start the Condensate stack: `./start.sh` (from repo root)
2. Open the admin dashboard: [http://localhost:3010](http://localhost:3010)
3. Go to **API Keys** → **Create Key**
4. Copy the `sk-...` key and set it as `CONDENSATE_API_KEY`

## Self-Hosting

The MCP bridge connects to your own Condensate server. See the [main README](../../README.md#getting-started) for Docker Compose setup.

For a cloud-hosted Condensate instance, replace `http://localhost:8000` with your server URL.

## Running Manually (without npx)

```bash
git clone https://github.com/condensate-io/core
cd core/sdks/mcp-bridge
npm install
CONDENSATE_URL=http://localhost:8000 CONDENSATE_API_KEY=sk-xxx node index.js
```
