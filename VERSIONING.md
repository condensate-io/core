# Versioning Strategy

Condensate follows [Semantic Versioning 2.0.0](https://semver.org/).

## Version Format: `MAJOR.MINOR.PATCH`

-   **MAJOR**: Incompatible API changes or Breaking Spec changes.
-   **MINOR**: Backwards-compatible functionality additions.
-   **PATCH**: Backwards-compatible bug fixes.

## Unified Release Flow

Condensate uses a single-tag release strategy via GitHub Actions. A single git tag (e.g., `v0.1.0`) triggers a concurrent release across all primary ecosystems.

### Package Naming Conventions
- **Rust (crates.io)**: `condensate`
- **Python (PyPI)**: `condensate`
- **Node/npm (npmregistry)**: `@condensate/core` (CLI/MCP) and `@condensate/sdk` (Client library)

### Release Workflow
1. **Tagging**: Create a new semantic tag: `git tag -a v0.1.0 -m "Release v0.1.0" && git push origin v0.1.0`.
2. **Automated Publishing**:
   - CI builds and publishes `condensate` to PyPI.
   - CI builds and publishes `condensate` to crates.io.
   - CI builds and publishes `@condensate/core` and `@condensate/sdk` to npm.
3. **Draft Release**: A GitHub Release is automatically created with the bundled binaries and changelog notes.

## Stability Levels

-   **Experimental**: APIs may change at any time. (Current State)
-   **Alpha**: Feature complete, but unstable.
-   **Beta**: Stable API, focus on bug fixes.
-   **Stable**: Production ready.

## Deprecation Policy

Features will be marked as deprecated in a MINOR release and removed in the next MAJOR release. a minimum of one release cycle warning is required.
