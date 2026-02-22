# Configuration Guide

Condensate can be tuned via environment variables and the dynamic settings UI.

## Environment Variables

Edit the `.env` file in the project root:

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_BASE_URL` | Default LLM API endpoint. | `http://localhost:11434/v1` |
| `LLM_MODEL` | Default model identifier. | `phi3` |
| `POSTGRES_DB` | Main database name. | `condensate` |
| `QDRANT_URL` | Vector store endpoint. | `http://condensate-vector:6333` |
| `ADMIN_USERNAME` | Admin dash user. | `admin` |
| `ADMIN_PASSWORD` | Admin dash password. | `admin` |

## HITL Assertion Review

Condensate includes a Human-in-the-Loop review system to ensure only safe, accurate assertions enter long-term memory.

### Review Mode

| Variable | Description | Default |
|----------|-------------|---------|
| `REVIEW_MODE` | `manual` (all assertions require human approval) or `auto` (guardrails only, no human step). | `manual` |

**Manual mode** is recommended for production deployments where data integrity is critical. **Auto mode** is suitable for trusted internal data sources where throughput is more important than oversight.

### Guardrail Thresholds

| Variable | Description | Default |
|----------|-------------|---------|
| `INSTRUCTION_BLOCK_THRESHOLD` | Assertions with an `instruction_score` at or above this value are automatically rejected. Range: `0.0`–`1.0`. Higher = more permissive. | `0.5` |
| `SAFETY_BLOCK_THRESHOLD` | Assertions with a `safety_score` at or above this value are automatically rejected. Range: `0.0`–`1.0`. Higher = more permissive. | `0.7` |

### Tuning Guidance

| Use Case | `INSTRUCTION_BLOCK_THRESHOLD` | `SAFETY_BLOCK_THRESHOLD` | `REVIEW_MODE` |
|----------|-------------------------------|--------------------------|---------------|
| Enterprise / compliance | `0.3` | `0.5` | `manual` |
| General purpose | `0.5` | `0.7` | `manual` |
| Trusted internal data | `0.8` | `0.9` | `auto` |
| Personal knowledge base | `0.9` | `0.9` | `auto` |

### Review Queue API

When `REVIEW_MODE=manual`, assertions accumulate in a review queue accessible via:

```
GET  /api/admin/review/assertions/pending
POST /api/admin/review/assertions/{id}/approve
POST /api/admin/review/assertions/{id}/reject
POST /api/admin/review/assertions/bulk-approve
```

The Admin Dashboard's **Review Queue** tab provides a UI for these operations with guardrail score visualization.

For full details, see the [HITL Whitepaper](../whitepaper_hitl.md).

## Dynamic LLM Switching

The system supports **hot-swapping** models without a restart via the Admin Dashboard's **LLM Settings** tab.

- **Note**: Changing models affects the quality of future "Condensations" but does not retroactively change existing assertions unless a "Retroactive Learning" job is triggered.

## Hardware Recommendations

- **Local (Ollama)**: Minimum 16GB RAM and an Apple M-series chip or NVIDIA GPU (8GB+ VRAM) for acceptable phi3 performance.
- **Cloud**: Minimal local compute required; handles thousands of memories per project with standard hardware.
