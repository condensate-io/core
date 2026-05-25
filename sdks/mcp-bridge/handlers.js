/**
 * HTTP tool handlers for the Condensate MCP bridge.
 * @param {string | undefined} apiKey
 * @returns {Record<string, string>}
 */
export function buildRequestHeaders(apiKey) {
    const headers = {
        "Content-Type": "application/json",
    };
    if (apiKey) {
        headers["Authorization"] = `Bearer ${apiKey}`;
    }
    return headers;
}

/**
 * @param {string} toolName
 * @param {Record<string, unknown>} args
 * @param {{ axios: import("axios").AxiosInstance; condensateUrl: string; apiKey: string | undefined }} deps
 * @returns {Promise<{ content: Array<{ type: string; text: string }> }>}
 */
export async function executeToolCall(toolName, args, deps) {
    const { axios, condensateUrl, apiKey } = deps;
    const headers = buildRequestHeaders(apiKey);

    if (toolName === "add_memory") {
        const endpoint = `${condensateUrl}/api/v1/episodic`;
        const payload = {
            text: args.text,
            source: args.source || "mcp_bridge",
            project_id: args.project_id || "default",
            metadata: { client: "mcp-bridge" },
        };

        const response = await axios.post(endpoint, payload, { headers });
        return {
            content: [{ type: "text", text: `Memory added. ID: ${response.data.id}` }],
        };
    }

    if (toolName === "retrieve_memory") {
        const endpoint = `${condensateUrl}/api/v1/memory/retrieve`;
        const payload = {
            query: args.query,
        };

        const response = await axios.post(endpoint, payload, { headers });
        return {
            content: [{ type: "text", text: response.data.answer }],
        };
    }

    if (toolName === "start_task_session") {
        const task_id = args.task_id;
        const agent_id = args.agent_id;
        const agent_role = args.agent_role;
        const episodicEndpoint = `${condensateUrl}/api/v1/episodic`;

        await axios.post(
            episodicEndpoint,
            {
                text: `Lifecycle Start: Task ${task_id} started by agent ${agent_id || "unknown"} (${agent_role || "developer"})`,
                source: "mcp_bridge",
                project_id: "default",
                metadata: {
                    event_type: "lifecycle_start",
                    task_id,
                    agent_id,
                    agent_role,
                },
            },
            { headers }
        );

        const retrieveEndpoint = `${condensateUrl}/api/v1/memory/retrieve`;
        const response = await axios.post(
            retrieveEndpoint,
            {
                query: `What is the context, memories, and policies for task ${task_id}?`,
            },
            { headers }
        );

        return {
            content: [
                {
                    type: "text",
                    text: `Task session started for ${task_id}. Initial Context:\n\n${response.data.answer}`,
                },
            ],
        };
    }

    if (toolName === "record_assertion") {
        const { subject_text, predicate, object_text, confidence } = args;
        const endpoint = `${condensateUrl}/api/v1/episodic`;

        const payload = {
            text: `Record assertion: ${subject_text} ${predicate} ${object_text}`,
            source: "mcp_bridge",
            project_id: "default",
            metadata: {
                event_type: "record_assertion",
                subject_text,
                predicate,
                object_text,
                confidence: confidence !== undefined ? confidence : 1.0,
            },
        };

        const response = await axios.post(endpoint, payload, { headers });
        return {
            content: [{ type: "text", text: `Structured assertion recorded. ID: ${response.data.id}` }],
        };
    }

    if (toolName === "checkpoint_state") {
        const state_dump = args.state_dump;
        const endpoint = `${condensateUrl}/api/v1/episodic`;

        const payload = {
            text: `Checkpointing execution state`,
            source: "mcp_bridge",
            project_id: "default",
            metadata: {
                event_type: "checkpoint_state",
                state_dump,
            },
        };

        const response = await axios.post(endpoint, payload, { headers });
        return {
            content: [{ type: "text", text: `Checkpoint created. ID: ${response.data.id}` }],
        };
    }

    throw new Error(`Unknown tool: ${toolName}`);
}
