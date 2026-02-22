# condensate (Rust SDK)

Official Rust client for [Condensate](https://condensate.io) — the open-source Agent Memory System.

[![crates.io](https://img.shields.io/crates/v/condensate)](https://crates.io/crates/condensate)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](../../LICENSE)

## Installation

Add to your `Cargo.toml`:

```toml
[dependencies]
condensate = "0.1.0"
tokio = { version = "1", features = ["full"] }
uuid = { version = "1", features = ["v4"] }
```

## Quick Start

```rust
use condensate::{CondensateClient, EpisodicItem};
use uuid::Uuid;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = CondensateClient::new(
        std::env::var("CONDENSATE_URL")
            .unwrap_or_else(|_| "http://localhost:8000".to_string()),
        std::env::var("CONDENSATE_API_KEY").ok(),
    );

    // Store a memory
    client.add_item(&EpisodicItem {
        project_id: Uuid::new_v4(),
        source: "api".to_string(),
        text: "The team decided to use PostgreSQL for the primary store.".to_string(),
        metadata: Default::default(),
    })?;

    println!("Memory stored successfully.");
    Ok(())
}
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|---|---|---|
| `CONDENSATE_URL` | Base URL of your Condensate server | `http://localhost:8000` |
| `CONDENSATE_API_KEY` | API key from the admin dashboard | — |

### Client Constructor

```rust
let client = CondensateClient::new(
    "https://memory.yourcompany.com".to_string(), // base_url
    Some("sk-prod-xxxx".to_string()),             // api_key (None to disable auth)
);
```

## API Reference

### `add_item(item: &EpisodicItem) -> Result<(), CondensateError>`

Stores a raw episodic memory item.

```rust
use condensate::EpisodicItem;
use uuid::Uuid;
use std::collections::HashMap;

let mut metadata = HashMap::new();
metadata.insert("source".to_string(), serde_json::json!("meeting"));

client.add_item(&EpisodicItem {
    project_id: Uuid::parse_str("550e8400-e29b-41d4-a716-446655440000")?,
    source: "api".to_string(),
    text: "Alice approved the Q3 roadmap.".to_string(),
    metadata,
})?;
```

### Types

```rust
pub struct EpisodicItem {
    pub project_id: Uuid,
    pub source: String,      // "api" | "chat" | "note" | "tool"
    pub text: String,
    pub metadata: HashMap<String, serde_json::Value>,
}
```

## Building the CLI Binary

The Rust SDK also ships a standalone CLI binary built by the release workflow:

```bash
cd sdks/rust
cargo build --release
./target/release/condensate --help
```

Pre-built binaries for Linux x64, macOS x64/arm64, and Windows x64 are attached to each [GitHub Release](https://github.com/condensate-io/core/releases).

## Getting Your API Key

1. Start the Condensate stack: `./start.sh` (from repo root)
2. Open the admin dashboard: [http://localhost:3010](http://localhost:3010)
3. Go to **API Keys** → **Create Key**
4. Copy the `sk-...` key

## Self-Hosting

See the [main README](../../README.md#getting-started) for Docker Compose setup.
