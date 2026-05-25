import { test } from 'node:test';
import assert from 'node:assert/strict';
import axios from 'axios';
import { CondensatesClient, ItemBuilder } from './index';
import type { EpisodicItem } from './index';

test('ItemBuilder.build throws when text is missing', () => {
    const builder = new ItemBuilder('550e8400-e29b-41d4-a716-446655440000');
    assert.throws(() => builder.build(), /Missing required fields/);
});

test('ItemBuilder.build returns episodic shape with chaining', () => {
    const projectId = '550e8400-e29b-41d4-a716-446655440000';
    const item = new ItemBuilder(projectId)
        .source('tool')
        .text('Captured thought')
        .metadata('severity', 'low')
        .build();

    assert.equal(item.project_id, projectId);
    assert.equal(item.source, 'tool');
    assert.equal(item.text, 'Captured thought');
    assert.ok(item.occurred_at);
    assert.equal(item.metadata?.severity, 'low');
});

test('CondensatesClient constructor passes base URL and bearer to axios.create', async (t) => {
    const post = t.mock.fn(async () => ({ data: { id: 'x' } }));
    const get = t.mock.fn();

    let capturedConfig: Parameters<typeof axios.create>[0] | undefined;
    t.mock.method(axios, 'create', (config: Parameters<typeof axios.create>[0]) => {
        capturedConfig = config;
        return { post, get } as unknown as ReturnType<typeof axios.create>;
    });

    new CondensatesClient('https://memory.example/', 'sekret');

    assert.equal(capturedConfig?.baseURL, 'https://memory.example/');
    assert.equal((capturedConfig?.headers as Record<string, string>)?.['Content-Type'], 'application/json');
    assert.equal((capturedConfig?.headers as Record<string, string>)?.Authorization, 'Bearer sekret');
});

test('CondensatesClient omits bearer when api key omitted', async (t) => {
    const post = t.mock.fn(async () => ({ data: { id: 'x' } }));
    const get = t.mock.fn();

    let capturedConfig: Parameters<typeof axios.create>[0] | undefined;
    t.mock.method(axios, 'create', (config: Parameters<typeof axios.create>[0]) => {
        capturedConfig = config;
        return { post, get } as unknown as ReturnType<typeof axios.create>;
    });

    new CondensatesClient('https://memory.example/');

    const headers = capturedConfig?.headers as Record<string, string | undefined>;
    assert.equal(headers?.Authorization, undefined);
});

test('CondensatesClient.addItem POSTs episodic payload with defaults', async (t) => {
    let url = '';
    let body: Record<string, unknown> | undefined;
    const post = t.mock.fn(async (endpoint: string, payload: Record<string, unknown>) => {
        url = endpoint;
        body = payload;
        return { data: { id: 'added-1' } };
    });
    const get = t.mock.fn();
    t.mock.method(axios, 'create', () => ({ post, get }) as unknown as ReturnType<typeof axios.create>);

    const client = new CondensatesClient('https://memory.example/', 'key');
    const result = await client.addItem({
        text: 'hello episodic world',
        source: 'chatgpt_export',
        metadata: { thread: 't-99' },
    });

    assert.equal(result.id, 'added-1');
    assert.equal(url, '/api/v1/episodic');
    assert.equal(body?.project_id, '00000000-0000-0000-0000-000000000000');
    assert.equal(body?.source, 'chatgpt_export');
    assert.equal(body?.text, 'hello episodic world');
    assert.deepEqual(body?.metadata, { thread: 't-99' });
    assert.equal(body?.occurred_at, undefined);
});

test('CondensatesClient.addItem uses explicit project_id and occurred_at', async (t) => {
    let body: EpisodicItem | Record<string, unknown> | undefined;
    const post = t.mock.fn(async (_endpoint: string, payload: EpisodicItem) => {
        body = payload;
        return { data: { id: 'z' } };
    });
    const get = t.mock.fn();
    t.mock.method(axios, 'create', () => ({ post, get }) as unknown as ReturnType<typeof axios.create>);

    const client = new CondensatesClient('https://memory.example/');
    await client.addItem({
        project_id: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
        text: 't',
        source: '',
        occurred_at: '2024-05-01T12:00:00.000Z',
    });

    assert.equal((body as { project_id: string }).project_id, 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee');
    assert.equal((body as { source: string }).source, 'api');
    assert.equal((body as { occurred_at?: string }).occurred_at, '2024-05-01T12:00:00.000Z');
});

test('CondensatesClient.addLifecycleEvent forwards structured metadata via addItem', async (t) => {
    let body: Record<string, unknown> | undefined;
    const post = t.mock.fn(async (_endpoint: string, payload: Record<string, unknown>) => {
        body = payload;
        return { data: { id: 'life-7' } };
    });
    const get = t.mock.fn();
    t.mock.method(axios, 'create', () => ({ post, get }) as unknown as ReturnType<typeof axios.create>);

    const client = new CondensatesClient('https://memory.example/');
    const result = await client.addLifecycleEvent(
        'custom_gate',
        'task-abc',
        'agent-xyz',
        'gate passed',
        { extra: 42 },
    );

    assert.equal(result.id, 'life-7');
    assert.equal(body?.source, 'orchestrator');
    assert.equal(body?.text, 'gate passed');
    const meta = body?.metadata as Record<string, unknown>;
    assert.equal(meta.event_type, 'custom_gate');
    assert.equal(meta.task_id, 'task-abc');
    assert.equal(meta.agent_id, 'agent-xyz');
    assert.equal(meta.extra, 42);
});

test('CondensatesClient.queryAssertions maps admin learning rows', async (t) => {
    const post = t.mock.fn();
    const get = t.mock.fn(async (_url: string) => ({
        data: [
            {
                id: 'lrn-1',
                project_id: 'p1',
                statement: 'Water boils at 100C',
                confidence: 0.91,
                status: 'active',
            },
        ],
    }));
    t.mock.method(axios, 'create', () => ({ post, get }) as unknown as ReturnType<typeof axios.create>);

    const client = new CondensatesClient('https://memory.example/');
    const assertions = await client.queryAssertions('ignored', 5);

    assert.equal(get.mock.calls.length, 1);
    assert.equal(get.mock.calls[0]?.arguments[0], '/api/admin/learnings');

    assert.equal(assertions.length, 1);
    assert.equal(assertions[0]?.id, 'lrn-1');
    assert.equal(assertions[0]?.project_id, 'p1');
    assert.equal(assertions[0]?.predicate, 'unknown');
    assert.equal(assertions[0]?.formatted_statement, 'Water boils at 100C');
    assert.equal(assertions[0]?.confidence, 0.91);
    assert.equal(assertions[0]?.status, 'active');
});
