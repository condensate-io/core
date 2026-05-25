/**
 * MCP tool catalog helpers — merge HTTP server tools with bridge-only tools.
 */

import { buildRequestHeaders } from "./handlers.js";

/** Tools implemented locally in the bridge (not on HTTP /mcp/tools). */
export const BRIDGE_ONLY_TOOLS = [
    {
        name: "retrieve_memory",
        description: "Retrieve knowledge from Condensate via the memory router.",
        inputSchema: {
            type: "object",
            properties: { query: { type: "string" } },
            required: ["query"],
        },
    },
    {
        name: "add_memory",
        description: "Alias for store_memory — add a raw episodic item.",
        inputSchema: {
            type: "object",
            properties: {
                text: { type: "string" },
                source: { type: "string", default: "user" },
                project_id: { type: "string" },
            },
            required: ["text"],
        },
    },
    {
        name: "start_task_session",
        description: "Start a task session and retrieve initial context.",
        inputSchema: {
            type: "object",
            properties: {
                task_id: { type: "string" },
                agent_id: { type: "string" },
                agent_role: { type: "string" },
            },
            required: ["task_id"],
        },
    },
    {
        name: "record_assertion",
        description: "Record a structured decision or observation.",
        inputSchema: {
            type: "object",
            properties: {
                subject_text: { type: "string" },
                predicate: { type: "string" },
                object_text: { type: "string" },
                confidence: { type: "number", default: 1.0 },
            },
            required: ["subject_text", "predicate", "object_text"],
        },
    },
    {
        name: "checkpoint_state",
        description: "Checkpoint agent execution state for fault tolerance.",
        inputSchema: {
            type: "object",
            properties: { state_dump: { type: "object" } },
            required: ["state_dump"],
        },
    },
];

export const SERVER_PROXY_TOOL_NAMES = new Set([
    "store_memory",
    "add_data_source",
    "trigger_data_source",
    "query_graph",
    "get_context_analytics",
]);

/**
 * @param {import("axios").AxiosInstance} axios
 * @param {string} condensateUrl
 * @param {string | undefined} apiKey
 */
export async function fetchServerTools(axios, condensateUrl, apiKey) {
    const headers = buildRequestHeaders(apiKey);
    const response = await axios.get(`${condensateUrl}/mcp/tools`, { headers, timeout: 5000 });
    return response.data;
}

/** @param {Array<{ name: string }>} serverTools @param {Array<{ name: string }>} bridgeTools */
export function mergeToolCatalog(serverTools, bridgeTools) {
    const seen = new Set(serverTools.map((t) => t.name));
    const merged = [...serverTools];
    for (const tool of bridgeTools) {
        if (!seen.has(tool.name)) {
            merged.push(tool);
            seen.add(tool.name);
        }
    }
    return merged;
}

/**
 * @param {string} toolName
 * @param {Record<string, unknown>} args
 * @param {{ axios: import("axios").AxiosInstance; condensateUrl: string; apiKey: string | undefined }} deps
 */
export async function proxyServerToolCall(toolName, args, deps) {
    const headers = buildRequestHeaders(deps.apiKey);
    const response = await deps.axios.post(
        `${deps.condensateUrl}/mcp/tools/call`,
        { name: toolName, arguments: args },
        { headers }
    );
    return response.data;
}

/** Map bridge-local names to HTTP server tool names + argument shape. */
export function mapToServerTool(toolName, args) {
    if (toolName === "add_memory") {
        return {
            name: "store_memory",
            arguments: {
                content: args.text,
                type: "episodic",
                project_id: args.project_id,
                metadata: { source: args.source || "mcp_bridge", client: "mcp-bridge" },
            },
        };
    }
    return { name: toolName, arguments: args };
}
