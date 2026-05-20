import { CondensatesClient } from './index';

export class CondensateOrchestrationHooks {
    private client: CondensatesClient;

    constructor(client: CondensatesClient) {
        this.client = client;
    }

    /**
     * Log the start of an autonomous agent execution session.
     */
    async onAgentStarted(taskId: string, agentId: string, agentRole: string = 'developer'): Promise<{ id: string }> {
        const text = `Lifecycle Event: Task ${taskId} started by agent ${agentId} (${agentRole})`;
        const metadata = {
            event_type: 'lifecycle_start',
            task_id: taskId,
            agent_id: agentId,
            agent_role: agentRole
        };
        return this.client.addItem({
            text,
            source: 'orchestrator',
            metadata
        });
    }

    /**
     * Log agent suspension, checkpointing its current execution state for resume/hand-off.
     */
    async onAgentSuspended(taskId: string, agentId: string, stateDump: Record<string, any>): Promise<{ id: string }> {
        const text = `Lifecycle Event: Task ${taskId} suspended by agent ${agentId} (checkpoint saved)`;
        const metadata = {
            event_type: 'lifecycle_suspend',
            task_id: taskId,
            agent_id: agentId,
            state_dump: stateDump
        };
        return this.client.addItem({
            text,
            source: 'orchestrator',
            metadata
        });
    }

    /**
     * Log agent resumption.
     */
    async onAgentResumed(taskId: string, agentId: string): Promise<{ id: string }> {
        const text = `Lifecycle Event: Task ${taskId} resumed by agent ${agentId}`;
        const metadata = {
            event_type: 'lifecycle_resume',
            task_id: taskId,
            agent_id: agentId
        };
        return this.client.addItem({
            text,
            source: 'orchestrator',
            metadata
        });
    }

    /**
     * Log agent crash for fault tolerance tracing and recovery.
     */
    async onAgentCrashed(taskId: string, agentId: string, error: string, stateDump?: Record<string, any>): Promise<{ id: string }> {
        const text = `Lifecycle Event: Task ${taskId} crashed for agent ${agentId}. Error: ${error}`;
        const metadata: Record<string, any> = {
            event_type: 'lifecycle_crash',
            task_id: taskId,
            agent_id: agentId,
            error
        };
        if (stateDump) {
            metadata.state_dump = stateDump;
        }
        return this.client.addItem({
            text,
            source: 'orchestrator',
            metadata
        });
    }

    /**
     * Log task completion, summarizing findings for future agent hand-offs.
     */
    async onAgentCompleted(taskId: string, agentId: string, finalFindings: string): Promise<{ id: string }> {
        const text = `Lifecycle Event: Task ${taskId} completed by agent ${agentId}. Findings: ${finalFindings}`;
        const metadata = {
            event_type: 'lifecycle_complete',
            task_id: taskId,
            agent_id: agentId,
            final_findings: finalFindings
        };
        return this.client.addItem({
            text,
            source: 'orchestrator',
            metadata
        });
    }
}
