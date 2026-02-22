# Edge API Reference (V1)

The Edge API provides a structured interface for developers to build applications on top of the Condensate Memory System.

**Base URL**: `http://localhost:8000/api/v1`
**Authentication**: `Authorization: Bearer <API_KEY>`

---

## 1. Episodic Store
Access the raw, immutable history of ingested events.

### `GET /episodic`
List raw memories with optional filtering.

**Query Parameters:**
- `project_id` (UUID): Filter by project scope.
- `source` (string): Filter by source type (e.g., `chat`, `github`).
- `limit` (int): Max records (default 100).

---

## 2. Learning Graph
Inspect canonical entities and synthesized facts.

### `GET /graph/entities`
Retrieve resolved entities (People, Systems, Concepts).
- **Filter**: `project_id`, `type`.

### `GET /graph/assertions`
Retrieve structured factual claims.
- **Filter**: `project_id`, `subject` (partial text match).

---

## 3. Ingestion Control
Manage and trigger data processing jobs.

### `POST /ingest/jobs`
Create a new ingestion job.
```json
{
  "project_id": "uuid-here",
  "source_type": "web",
  "source_config": { "url": "https://example.com/docs" },
  "trigger_type": "on_demand"
}
```

### `POST /ingest/jobs/{id}/run`
Trigger an immediate execution of a defined job.

---

## 4. Data Portability

### `GET /export/jsonl`
Export the entire memory and graph state for a project in JSONL format. Useful for backups, fine-tuning, or migrating to other cognitive architectures.
- **Response Type**: `application/x-jsonlines`
