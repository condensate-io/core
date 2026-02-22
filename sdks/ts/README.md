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

## Building from Source

```bash
cd sdks/ts
npm install
npm run build   # outputs to dist/
```

## Self-Hosting

See the [main README](../../README.md#getting-started) for Docker Compose setup.
