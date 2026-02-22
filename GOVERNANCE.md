# Governance Model

The **Condensate** project (incorporating `agent-memory-spec`, `agent-memory-kernel`, and `agent-memory-enterprise`) is an open-source initiative dedicated to standardizing agentic memory systems.

## 1. Project Roles

### Maintainers
Maintainers have write access to the repository and are responsible for:
-   Reviewing Module Proposals (RFCs).
-   Merging pull requests.
-   Managing the release cycle.
-   Enforcing the Code of Conduct.

### Contributors
Contributors are community members who prompt issues, submit PRs, or improve documentation.

## 2. Decision Making Process

Technical decisions follow a **Consensus-Seeking** model.

### RFC Process
Major changes to the Specification (`/spec`) or Kernel (`/src`) must go through the **Request for Comments (RFC)** process:
1.  **Draft**: Submit a PR with a new file in `rfcs/XXXX-my-feature.md`.
2.  **Discussion**: The community discusses the proposal on the PR.
3.  **Approval**: A Maintainer must approve the RFC.
4.  **Implementation**: Once approved, implementation can begin.

## 3. Code of Conduct

We are committed to providing a friendly, safe and welcoming environment for all, regardless of gender, sexual orientation, disability, ethnicity, religion, or similar personal characteristic.

Please read and adhere to our [Code of Conduct](CODE_OF_CONDUCT.md).

## 4. License

This project is dual-licensed:
-   **Specs & RFCs**: Apache 2.0 (Open Spec)
-   **Kernel**: Apache 2.0 (OSS Core)
-   **Enterprise Modules**: Proprietary (Closed Source)
