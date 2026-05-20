import axios, { AxiosInstance } from 'axios';

export { CondensateOrchestrationHooks } from './lifecycle';

/**
 * Episodic Item Schema (V2)
 * Corresponds to src/db/schemas.py EpisodicItemCreate
 */
export interface EpisodicItem {
    id?: string;
    project_id?: string;
    source: string; // chatgpt_export | api | tool | note
    text: string;
    occurred_at?: string; // ISO-8601
    metadata?: Record<string, any>;
}

export interface Assertion {
    id: string;
    project_id: string;
    subject_text?: string;
    predicate: string;
    object_text?: string;
    confidence: number;
    status: 'active' | 'superseded' | 'contested';
    formatted_statement?: string; // For display convenience
}

export class CondensatesClient {
    private client: AxiosInstance;

    constructor(baseURL: string, apiKey?: string) {
        this.client = axios.create({
            baseURL,
            headers: {
                'Content-Type': 'application/json',
                ...(apiKey && { 'Authorization': `Bearer ${apiKey}` })
            }
        });
    }

    /**
     * Ingest a new Episodic Item into the Episodic Store.
     * @param item The raw item data.
     */
    async addItem(item: EpisodicItem): Promise<{ id: string }> {
        const payload = {
            project_id: item.project_id || '00000000-0000-0000-0000-000000000000',
            source: item.source || 'api',
            text: item.text,
            metadata: item.metadata || {},
            occurred_at: item.occurred_at
        };
        const response = await this.client.post('/api/v1/episodic', payload);
        return response.data;
    }

    /**
     * Standardize injection of event_type metadata for Symphony-like orchestrations.
     */
    async addLifecycleEvent(
        eventType: string,
        taskId: string,
        agentId: string,
        text: string,
        metadata?: Record<string, any>
    ): Promise<{ id: string }> {
        const fullMetadata = {
            event_type: eventType,
            task_id: taskId,
            agent_id: agentId,
            ...(metadata || {})
        };
        return this.addItem({
            text,
            source: 'orchestrator',
            metadata: fullMetadata
        });
    }

    /**
     * Search for Assertions (formerly Learnings).
     * @param query The search query.
     * @param limit Max results.
     */
    async queryAssertions(query?: string, limit: number = 20): Promise<Assertion[]> {
        // Currently admin.py exposes GET /learnings (returns all) or POST /vectors (search)
        // For semantic search we might use a different endpoint in future, but for now:
        const response = await this.client.get('/api/admin/learnings');

        // Transform response to match Assertion interface if needed
        // The API returns: { id, statement, confidence, status... }
        return response.data.map((r: any) => ({
            id: r.id,
            project_id: r.project_id,
            predicate: 'unknown', // API view might just return 'statement' string
            formatted_statement: r.statement,
            confidence: r.confidence,
            status: r.status
        }));
    }
}

/**
 * Helper to construct valid EpisodicItems
 */
export class ItemBuilder {
    private item: Partial<EpisodicItem> = {
        metadata: {}
    };

    constructor(projectId: string) {
        this.item.project_id = projectId;
        this.item.occurred_at = new Date().toISOString();
        this.item.source = 'api';
    }

    source(source: string): this {
        this.item.source = source;
        return this;
    }

    text(text: string): this {
        this.item.text = text;
        return this;
    }

    metadata(key: string, value: any): this {
        if (!this.item.metadata) this.item.metadata = {};
        this.item.metadata[key] = value;
        return this;
    }

    build(): EpisodicItem {
        if (!this.item.project_id || !this.item.text) {
            throw new Error("Missing required fields: project_id, text");
        }
        return this.item as EpisodicItem;
    }
}
