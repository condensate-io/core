import { CondensatesClient, EpisodicItem } from './index';
import { CondensateOrchestrationHooks } from './lifecycle';

// Simple unit test verification script
async function runTests() {
    console.log("Running TS SDK Lifecycle Hooks verification...");

    const mockClient = {
        addItem: async (item: EpisodicItem) => {
            console.log("Mock Client received:", JSON.stringify(item, null, 2));
            return { id: "item-123" };
        }
    } as unknown as CondensatesClient;

    const hooks = new CondensateOrchestrationHooks(mockClient);

    const started = await hooks.onAgentStarted("task-1", "agent-abc", "orchestrator");
    if (started.id !== "item-123") throw new Error("onAgentStarted failed");

    const stateDump = { current_file: "index.ts", progress: 0.8 };
    const suspended = await hooks.onAgentSuspended("task-1", "agent-abc", stateDump);
    if (suspended.id !== "item-123") throw new Error("onAgentSuspended failed");

    const resumed = await hooks.onAgentResumed("task-1", "agent-abc");
    if (resumed.id !== "item-123") throw new Error("onAgentResumed failed");

    const crashed = await hooks.onAgentCrashed("task-1", "agent-abc", "Connection lost", stateDump);
    if (crashed.id !== "item-123") throw new Error("onAgentCrashed failed");

    const completed = await hooks.onAgentCompleted("task-1", "agent-abc", "All tasks succeeded");
    if (completed.id !== "item-123") throw new Error("onAgentCompleted failed");

    console.log("TS SDK Lifecycle Hooks tests PASSED successfully.");
}

runTests().catch(err => {
    console.error("Test failed:", err);
    process.exit(1);
});
