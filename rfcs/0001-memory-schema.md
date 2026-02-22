# RFC 0001: Strict Memory Schema

| Metadata | Value |
| :--- | :--- |
| **RFC ID** | 0001 |
| **Title** | Strict Memory Schema |
| **Status** | Accepted |
| **Created** | 2026-02-17 |
| **Authors** | Neeraj |

## Summary

This RFC defines the strict JSON schema for all memory artifacts within the Condensate system. It mandates that no raw text is trusted; all inputs and outputs must be typed, validated, and hashed.

## Motivation

Agents often suffer from hallucination and drift. By strictly typing memory into "Events" (Episodic) and "Learnings" (Semantic), and enforcing a rigid schema, we can build a deterministic "Memory Condensation OS".

## Data Model

### 1. EpisodicItem (Raw Memory)

Raw, immutable record of an occurrence.

```json
{
  "id": "uuid-v4",
  "project_id": "uuid-v4",
  "source": "chatgpt_export | api | tool | note",
  "text": "Raw text content...",
  "occurred_at": "ISO-8601",
  "metadata": {
    "source_id": "external-id",
    "actor_id": "actor-id"
  },
  "qdrant_point_id": "uuid-v4"
}
```

### 2. Assertion (Semantic Knowledge)

A distilled, atomic claim or fact derived from items.

```json
{
  "id": "uuid-v4",
  "project_id": "uuid-v4",
  "subject_text": "Billing API",
  "predicate": "requires",
  "object_text": "idempotency keys",
  "confidence": 0.95,
  "status": "active | superseded | contested",
  "provenance": [
    { "episodic_id": "uuid-1", "quote": "..." }
  ]
}
```

### 3. MemoryPack (Operational)

A collection of learnings compiled for a specific agent role.

```json
{
  "id": "uuid-v4",
  "pack_type": "coding_agent | reviewer | sre | compliance",
  "target_role": "backend-developer",
  "learnings": [
    { "statement": "...", "confidence": 0.9 }
  ],
  "policies": [
    {
      "trigger": "file_change:*.py",
      "rule": "Must run black formatter",
      "priority": "high"
    }
  ]
}
```

## Validation

All ingress points must validate mapped JSON against strict Pydantic models. Invalid data is rejected or quarantined.
