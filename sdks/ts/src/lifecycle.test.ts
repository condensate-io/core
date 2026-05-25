import { test } from 'node:test';
import assert from 'node:assert/strict';
import { CondensateOrchestrationHooks } from './lifecycle';
import type { CondensatesClient, EpisodicItem } from './index';

function stubClient(onItem: (item: EpisodicItem) => void): CondensatesClient {
    return {
        async addItem(item: EpisodicItem) {
            onItem(item);
            return { id: 'stub-row' };
        },
    } as CondensatesClient;
}

test('CondensateOrchestrationHooks.onAgentStarted attaches lifecycle_start metadata', async () => {
    let captured: EpisodicItem | undefined;
    const hooks = new CondensateOrchestrationHooks(
        stubClient((item) => {
            captured = item;
        }),
    );

    const out = await hooks.onAgentStarted('task-9', 'agent-2', 'planner');

    assert.deepEqual(out, { id: 'stub-row' });
    assert.equal(captured?.source, 'orchestrator');
    assert.match(captured?.text ?? '', /Task task-9 started by agent agent-2 \(planner\)/);
    assert.equal(captured?.metadata?.event_type, 'lifecycle_start');
    assert.equal(captured?.metadata?.task_id, 'task-9');
    assert.equal(captured?.metadata?.agent_id, 'agent-2');
    assert.equal(captured?.metadata?.agent_role, 'planner');
});

test('CondensateOrchestrationHooks.onAgentSuspended persists state_dump', async () => {
    let captured: EpisodicItem | undefined;
    const hooks = new CondensateOrchestrationHooks(
        stubClient((item) => {
            captured = item;
        }),
    );
    const checkpoint = { step: 3, artifacts: ['/tmp/state.json'] };

    await hooks.onAgentSuspended('t-1', 'a-77', checkpoint);

    assert.equal(captured?.metadata?.event_type, 'lifecycle_suspend');
    assert.equal(captured?.metadata?.task_id, 't-1');
    assert.equal(captured?.metadata?.agent_id, 'a-77');
    assert.deepEqual(captured?.metadata?.state_dump, checkpoint);
});

test('CondensateOrchestrationHooks.onAgentResumed records resume metadata', async () => {
    let captured: EpisodicItem | undefined;
    const hooks = new CondensateOrchestrationHooks(
        stubClient((item) => {
            captured = item;
        }),
    );

    await hooks.onAgentResumed('task-r', 'agent-r');

    assert.equal(captured?.metadata?.event_type, 'lifecycle_resume');
    assert.equal(captured?.metadata?.task_id, 'task-r');
    assert.equal(captured?.metadata?.agent_id, 'agent-r');
    assert.match(captured?.text ?? '', /resumed/);
});

test('CondensateOrchestrationHooks.onAgentCrashed records error and optional state_dump', async () => {
    let first: EpisodicItem | undefined;
    let second: EpisodicItem | undefined;
    let call = 0;
    const hooks = new CondensateOrchestrationHooks(
        stubClient((item) => {
            call += 1;
            if (call === 1) first = item;
            else second = item;
        }),
    );

    await hooks.onAgentCrashed('t-crash', 'a-crash', 'oom');
    assert.equal(first?.metadata?.event_type, 'lifecycle_crash');
    assert.equal(first?.metadata?.error, 'oom');
    assert.equal(first?.metadata?.state_dump, undefined);

    const dump = { lastCommand: 'compile' };
    await hooks.onAgentCrashed('t-crash', 'a-crash', 'panic', dump);
    assert.deepEqual(second?.metadata?.state_dump, dump);
});

test('CondensateOrchestrationHooks.onAgentCompleted records final_findings', async () => {
    let captured: EpisodicItem | undefined;
    const hooks = new CondensateOrchestrationHooks(
        stubClient((item) => {
            captured = item;
        }),
    );

    await hooks.onAgentCompleted('t-done', 'a-done', 'Shipped GA');

    assert.equal(captured?.metadata?.event_type, 'lifecycle_complete');
    assert.equal(captured?.metadata?.final_findings, 'Shipped GA');
    assert.match(captured?.text ?? '', /Findings: Shipped GA/);
});
