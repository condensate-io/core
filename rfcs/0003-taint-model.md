# RFC 0003: Taint Model & Trust Boundaries

| Metadata | Value |
| :--- | :--- |
| **RFC ID** | 0003 |
| **Title** | Taint Model |
| **Status** | Draft |
| **Created** | 2026-02-17 |

## Summary

This RFC defines a flow of "Taint" to prevent untrusted external inputs from corrupting high-integrity Core Memory.

## Trust Levels

1.  **Trusted (Red)**: Verified internal axioms. Manual overrides by admins. Hardcoded policies.
2.  **Internal (Orange)**: Inferred assertions from internal items (e.g. internal slack, closed PRs). High confidence but fallible.
3.  **Untrusted (Yellow)**: Inferred assertions from external items (e.g. public issues, external emails). Prone to injection/poisoning.
4.  **External (Blue)**: Raw user queries or web search results. ephemeral.

## Flow & Policy

-   **No Upward Contamination**: Information from `Untrusted` sources cannot overwrite `Trusted` or `Internal` memory without explicit Human-in-the-Loop (HITL) review.
-   **Taint Tracking**:
    -   If an `Assertion` is derived from a mix of `Internal` and `Untrusted` items, the resulting `Assertion` inherits the lowest trust level (`Untrusted`).
    -   `Taint` tags are propagated through the `ProofEnvelope`.

## Prompt Injection Mitigation

-   **Sandboxing**: Untrusted inputs are processed in separate "tainted" contexts.
-   **Schema Strictness**: The Extractor is forced to output JSON. It is instructed to classify "jailbreak attempts" as `risk_flags` rather than executing them.

```json
"risk_flags": [
    {
      "category": "prompt_injection",
      "severity": "high",
      "ref": "event_id_bad_input"
    }
]
```
