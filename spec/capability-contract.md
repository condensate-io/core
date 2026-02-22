# Specification: Capability Contract

Defines what an Agent *can* and *cannot* do based on the Memory Policy.

## 1. Policy Overlays

Memory is not just passive facts; it contains operational policies.

### 1.1 Trigger-Action Model
Policies are defined as:
`If (Context matches Trigger) THEN (Enforce Rule)`

**Example**:
-   **Trigger**: `file_path.endswith('.ts')`
-   **Rule**: `Use 'interface' instead of 'type'`
-   **Source**: `Assertion(id=123)` from `EpisodicItem(id=456)` (Code Review comment)

## 2. Resource Budgeting

(Planned for v2)
Policies can assume resource limits:
-   Max tokens per day.
-   Max tool calls per session.

## 3. Tool Access Control

Based on `Project` trust levels, agents may be granted or denied access to tools.
-   **Untrusted Context**: Deny `exec_shell`, Deny `write_file` (outside sandbox).
-   **Trusted Context**: Allow all.
