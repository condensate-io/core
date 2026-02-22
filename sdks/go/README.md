# condensate-go-sdk

Official Go client for [Condensate](https://condensate.io) — the open-source Agent Memory System.

[![Go Reference](https://pkg.go.dev/badge/github.com/condensate/condensate-go-sdk.svg)](https://pkg.go.dev/github.com/condensate/condensate-go-sdk)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](../../LICENSE)

## Installation

```bash
go get github.com/condensate/condensate-go-sdk
```

Requires Go 1.21+.

## Quick Start

```go
package main

import (
    "fmt"
    "log"
    "os"

    condensate "github.com/condensate/condensate-go-sdk"
)

func main() {
    client := condensate.NewClient(
        os.Getenv("CONDENSATE_URL"),     // e.g. "http://localhost:8000"
        os.Getenv("CONDENSATE_API_KEY"), // e.g. "sk-xxxx"
    )

    // Store a memory
    err := client.AddItem(condensate.EpisodicItem{
        ProjectID: "your-project-uuid",
        Source:    "api",
        Text:      "The team decided to use PostgreSQL for the primary store.",
        Metadata: map[string]interface{}{
            "source": "meeting",
        },
    })
    if err != nil {
        log.Fatal(err)
    }

    // Retrieve assertions (structured knowledge)
    assertions, err := client.QueryAssertions("database")
    if err != nil {
        log.Fatal(err)
    }
    for _, a := range assertions {
        fmt.Printf("[%.0f%%] %s\n", a.Confidence*100, a.Formatted)
    }
}
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|---|---|---|
| `CONDENSATE_URL` | Base URL of your Condensate server | `http://localhost:8000` |
| `CONDENSATE_API_KEY` | API key from the admin dashboard | — |

### Client Options

```go
client := condensate.NewClient(
    "https://memory.yourcompany.com", // baseURL
    "sk-prod-xxxx",                   // apiKey
)
// Default HTTP timeout: 60 seconds
```

## API Reference

### `AddItem(item EpisodicItem) error`

Stores a raw episodic memory item.

```go
err := client.AddItem(condensate.EpisodicItem{
    ProjectID: "550e8400-e29b-41d4-a716-446655440000",
    Source:    "api",       // "api" | "chat" | "note" | "tool"
    Text:      "Alice approved the Q3 roadmap.",
    OccurredAt: "2026-02-18T10:00:00Z", // optional ISO-8601
    Metadata: map[string]interface{}{
        "author": "alice",
    },
})
```

### `QueryAssertions(query string) ([]Assertion, error)`

Retrieves structured assertions (distilled knowledge) from the knowledge graph.

```go
assertions, err := client.QueryAssertions("roadmap")
for _, a := range assertions {
    fmt.Printf("%s — confidence: %.2f — status: %s\n",
        a.Formatted, a.Confidence, a.Status)
}
```

### Types

```go
type EpisodicItem struct {
    ProjectID  string                 // UUID of the project
    Source     string                 // Origin label
    Text       string                 // Raw memory content
    OccurredAt string                 // Optional ISO-8601 timestamp
    Metadata   map[string]interface{} // Arbitrary key-value metadata
}

type Assertion struct {
    ID          string
    ProjectID   string
    SubjectText string
    Predicate   string
    ObjectText  string
    Confidence  float64
    Status      string  // "approved" | "pending_review" | "rejected"
    Formatted   string  // Human-readable summary
}
```

## Getting Your API Key

1. Start the Condensate stack: `./start.sh` (from repo root)
2. Open the admin dashboard: [http://localhost:3010](http://localhost:3010)
3. Go to **API Keys** → **Create Key**
4. Copy the `sk-...` key

## Self-Hosting

See the [main README](../../README.md#getting-started) for Docker Compose setup.
