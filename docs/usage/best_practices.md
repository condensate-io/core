# Best Practices for Cognitive Memory

To ensure your agent's memory remains useful and accurate over time, follow these best practices.

## 1. High-Quality Ingress
While the system is robust, the "Garbage In, Garbage Out" rule still applies.
- **Contextualize**: When pushing manual memories, include the "Why" and "Who". E.g., instead of "Postgres is used", use "Team Alpha decided to use Postgres for the metadata microservice."
- **Use Source Types**: Correctly tagging sources (e.g., `source=meeting_notes`) helps the Condenser apply the correct priority.

## 2. Managing Entity Sprawl
If your graph looks like a "uniform cloud" without clear clusters:
- **Canonicalize Early**: Check the **Entities** tab regularly. If you see "PostgreSQL" and "Postgres" as separate nodes, use the API/UI to merge them.
- **Model Selection**: Switch to a larger model (e.g., GPT-4) occasionally for a "Deep Condensation" pass to clean up naming inconsistencies that smaller models might miss.

## 3. Cognitive Tuning
- **Heavier Weights**: If the agent is missing obvious connections during retrieval, increase the `HEBBIAN_REINFORCEMENT_RATE` in the backend to make relationships "strengthen" faster.
- **Pruning**: Don't be afraid to delete orphaned episodic items. The system will retain the distilled **Assertions** even if the raw raw evidence is pruned (though provenance links will break).

## 4. MCP for Agent Loops
When integrating with agents:
- **Immediate Feedback**: Have the agent call `store_memory` immediately after a critical decision is made.
- **Query First**: Before an agent starts a task, have it perform a `research` query to the Memory Router to "warm up" its context with relevant learnings from similar past tasks.
