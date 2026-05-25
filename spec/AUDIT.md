# Spec vs Implementation Audit

**Date:** 2026-05-25  
**Scope:** `spec/`, `rfcs/`, core `src/db/models.py`, Qdrant config, MCP surfaces

## Summary

| Area | Spec reference | Implementation | Status |
|------|----------------|----------------|--------|
| Vector dimensions | `spec/memory-schema.md` §2 — 384d | `src/db/qdrant.py`, `src/engine/bootstrap.py` — 384d FastEmbed | **Aligned** |
| Assertion status enum | `spec/memory-schema.md` — `active`, `superseded`, `contested` | `src/db/models.py` Assertion.status | **Aligned** |
| EpisodicItem schema | `spec/memory-schema.md` §1.2 | `src/db/models.py` EpisodicItem | **Aligned** |
| Cognitive provenance chain | `spec/cognitive-provenance.md` — evidence on every belief | Assertions carry `provenance` JSONB; optional empty in edge paths | **Partial** — HITL/auto paths should enforce non-empty provenance |
| Proof envelopes | RFC-0002 / `spec/cognitive-provenance.md` §3 | `src/engine/proof_envelope.py`, tests in `test_proof_envelope.py` | **Aligned** |
| Taint model RFC-0003 | Designed, not in spec tables | Not implemented in `src/` | **Gap** — tracked Tranche 4 Phase 3 |
| MCP HTTP tools | Tranche 5 — unified with stdio bridge | `src/server/mcp.py` list_tools (5 tools); bridge merges via `GET /mcp/tools` | **Aligned** (batch 2) |
| MCP JSON-RPC transport | Tranche 5 Phase 2 | HTTP uses REST `/mcp/tools`, not JSON-RPC 2.0 | **Gap** |
| API key storage | Roadmap Phase 1 — bcrypt at rest | `src/server/security.py` hash + prefix lookup | **Aligned** |
| Temporal assertions | Tranche 5 — `valid_from` / `valid_until` | Not on Assertion model | **Gap** |
| Learning vs Assertion naming | Older docs say "Learning" | Code and API use Assertion; admin `/learnings` is legacy view | **Doc drift** — rename in external docs only |

## Detailed notes

### memory-schema.md

- All eight core tables exist in Alembic migrations and `src/db/models.py`.
- Qdrant collection `episodic_chunks` uses 384-dimensional cosine vectors (BAAI/bge-small-en-v1.5 via fastembed).
- Secondary collection `semantic_assertions` also 384d in `src/db/qdrant.py`.

### cognitive-provenance.md

- Forward impact analysis (invalid event → downgrade dependents) is not fully automated; supersession handled in condenser/HITL paths only.
- Recommend: add integration test when event retraction lands.

### capability-contract.md / replay-semantics.md

- Replay semantics depend on episodic immutability — **Aligned** (EpisodicItem has no update path in API).
- Capability contract MCP tool surface now documented via live `GET /mcp/tools` response.

### Recommended follow-ups

1. Add `valid_from` / `valid_until` to Assertion (Tranche 5).
2. Implement RFC-0003 taint columns (Tranche 4).
3. Replace REST MCP wrapper with JSON-RPC 2.0 (Tranche 5).
4. Enforce non-empty provenance on auto-approved assertions in condenser.

**Audit method:** Static review of spec markdown vs `src/db/models.py`, `src/server/mcp.py`, `src/db/qdrant.py`, and roadmap tracker. Re-run after major schema or protocol changes.
