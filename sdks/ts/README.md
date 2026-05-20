# @condensate/sdk

Official TypeScript / Node.js client for [Condensate](https://condensate.io) — the open-source Agent Memory System.

[![npm](https://img.shields.io/npm/v/@condensate/sdk)](https://www.npmjs.com/package/@condensate/sdk)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](../../LICENSE)

## Installation

```bash
npm install @condensate/sdk
# or
yarn add @condensate/sdk
```

Requires Node.js 18+.

## Quick Start

```typescript
import { CondensateClient } from '@condensate/sdk';

const client = new CondensateClient({
  baseUrl: process.env.CONDENSATE_URL ?? 'http://localhost:8000',
  apiKey: process.env.CONDENSATE_API_KEY!,
});

// Store a memory
await client.storeMemory({
  content: 'The team decided to use PostgreSQL for the primary store.',
  type: 'episodic',
  metadata: { source: 'meeting', project: 'infra-v2' },
});

// Retrieve relevant memories
const result = await client.retrieve('What database did we choose?');
console.log(result.answer);
console.log(result.sources);   // string[] of episodic item IDs
console.log(result.strategy);  // "recall" | "research" | "meta"
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|---|---|---|
| `CONDENSATE_URL` | Base URL of your Condensate server | `http://localhost:8000` |
| `CONDENSATE_API_KEY` | API key (create one in the admin dashboard) | — |

### Constructor Options

```typescript
const client = new CondensateClient({
  baseUrl: 'https://memory.yourcompany.com',  // required
  apiKey: 'sk-prod-xxxx',                      // required
  timeout: 30_000,                             // optional, ms (default: 30000)
});
```

## API Reference

### `storeMemory(options)`

Stores a raw episodic item and triggers the full condensation pipeline.

```typescript
await client.storeMemory({
  content: 'Alice approved the Q3 roadmap.',
  type: 'episodic',       // 'episodic' | 'note' | 'event'
  metadata: {
    source: 'slack',
    channel: '#product',
  },
});
```

### `retrieve(query, options?)`

Routes the query through the Memory Router and returns a synthesised answer.

```typescript
const result = await client.retrieve('What did Alice approve?');
// {
//   answer: 'Alice approved the Q3 roadmap.',
//   sources: ['<uuid>', ...],
//   strategy: 'recall'
// }
```

### `addEpisodicItem(item)` *(low-level)*

Directly posts to the v1 episodic API endpoint.

```typescript
await client.addEpisodicItem({
  project_id: 'your-project-uuid',
  source: 'api',
  text: 'User prefers dark mode.',
});
```

## TypeScript Types

```typescript
interface StoreMemoryOptions {
  content: string;
  type?: 'episodic' | 'note' | 'event';
  metadata?: Record<string, unknown>;
}

interface RetrieveResult {
  answer: string;
  sources: string[];
  strategy: 'recall' | 'research' | 'meta';
}
```

### Orchestration Lifecycle Hooks (Symphony Orchestration)

To support stateful orchestration in Symphony-like multi-agent networks, the TS SDK exposes the `CondensateOrchestrationHooks` class:

```typescript
import { CondensatesClient, CondensateOrchestrationHooks } from '@condensate/sdk';

const client = new CondensatesClient('http://localhost:8000', 'sk-your-key');
const hooks = new CondensateOrchestrationHooks(client);

// When an agent execution session starts
await hooks.onAgentStarted('linear-ticket-101', 'agent-developer-1', 'developer');

// Checkpoint/Suspend state for fault-tolerance or hand-offs
const stateDump = {
  current_file: 'src/server/v1_api.py',
  cursor_position: 142,
  progress_percent: 65.5
};
await hooks.onAgentSuspended('linear-ticket-101', 'agent-developer-1', stateDump);

// Resume execution
await hooks.onAgentResumed('linear-ticket-101', 'agent-developer-1');

// If an agent encounters a fatal error / crashes
await hooks.onAgentCrashed('linear-ticket-101', 'agent-developer-1', 'Database connection timeout', stateDump);

// On successful task completion
await hooks.onAgentCompleted('linear-ticket-101', 'agent-developer-1', 'All security patches applied successfully.');
```

#### Under the Hood: Metadata-Driven Design
Every event emitted by `CondensateOrchestrationHooks` is sent to the `/api/v1/episodic` endpoint with `source` set to `"orchestrator"` and the payload's `metadata` dictionary populated with `event_type`, `task_id`, and `agent_id`. Since Condensate scopes queries to the API key's project, lifecycle states are 100% tenant-isolated, enabling trace-based analysis of multi-agent execution lifecycles.

## Building from Source

```bash
cd sdks/ts
npm install
npm run build   # outputs to dist/
```

## Self-Hosting

See the [main README](../../README.md#getting-started) for Docker Compose setup.
