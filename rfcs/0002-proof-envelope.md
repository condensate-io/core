# RFC 0002: Proof Envelope & Cryptographic Provenance

| Metadata | Value |
| :--- | :--- |
| **RFC ID** | 0002 |
| **Title** | Proof Envelope |
| **Status** | Draft |
| **Created** | 2026-02-17 |

## Summary

This RFC introduces a "Proof Envelope" to cryptographically bind "Assertions" to their source "Items". This ensures that every piece of knowledge in the system can be traced back to its origin with tamper-evident certainty.

## Motivation

In enterprise environments, it is crucial to know *why* an agent believes something. "Hallucination" is often just a breakdown in provenance. By hashing inputs and signing outputs, we create a chain of custody for cognition.

## The Envelope Structure

Every `Assertion` object is wrapped in a `ProofEnvelope`:

```json
{
  "payload": {
    "assertion_id": "uuid",
    "subject_text": "prod-db",
    "predicate": "is",
    "object_text": "read-only",
    "distilled_at": "2026-02-17T12:00:00Z"
  },
  "provenance": {
    "method": "llm-distillation",
    "model": "gpt-4-turbo",
    "input_hashes": [
      "sha256(item_1_text)",
      "sha256(item_2_text)"
    ]
  },
  "signature": "hmac_sha256(payload + provenance, system_secret)"
}
```

## Implementation

1.  **Hashing**: All `EpisodicItem` content is hashed (SHA-256) upon ingress.
2.  **Linking**: When the Condenser engine generates an `Assertion`, it must cite the `item_id`s.
3.  **Signing**: The system calculates the hash of the inputs and the generated output, creating a signature.
4.  **Verification**: Before an agent uses an `Assertion`, the system verifies the signature to ensure the `statement` hasn't been altered without re-distillation.

## Replay Semantics

This structure allows for **Deterministic Replay**. We can re-run the `distillation` job on the same `input_hashes` with the same `model` and verify if the output `statement` matches (within semantic similarity bounds).
