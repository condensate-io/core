#!/usr/bin/env node

/**
 * Condensate MCP Bridge
 * 
 * This is a lightweight Node.js wrapper that exposes the Condensate 
 * Python server as a standard MCP server over Stdio.
 * 
 * It allows "npx @condensate/core" to work instantly.
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import axios from "axios";

const CONDENSATE_URL = process.env.CONDENSATE_URL || "http://localhost:8000";
const API_KEY = process.env.CONDENSATE_API_KEY;

const server = new Server(
    {
        name: "condensate-mcp-bridge",
        version: "0.1.0",
    },
    {
        capabilities: {
            tools: {},
        },
    }
);

// Proxy Tool Listing
server.setRequestHandler(ListToolsRequestSchema, async () => {
    try {
        return {
            tools: [
                {
                    name: "add_memory",
                    description: "Add a raw memory item (chat log, observation) to Condensate.",
                    inputSchema: {
                        type: "object",
                        properties: {
                            text: { type: "string" },
                            source: { type: "string", default: "user" },
                            project_id: { type: "string" }
                        },
                        required: ["text"]
                    }
                },
                {
                    name: "retrieve_memory",
                    description: "Retrieve knowledge from Condensate.",
                    inputSchema: {
                        type: "object",
                        properties: {
                            query: { type: "string" }
                        },
                        required: ["query"]
                    }
                },
                {
                    name: "start_task_session",
                    description: "Start a task session for Symphony orchestration, logging the start event and retrieving initial context / policies.",
                    inputSchema: {
                        type: "object",
                        properties: {
                            task_id: { type: "string", description: "Unique task/ticket identifier (e.g. Linear-123)" },
                            agent_id: { type: "string", description: "Unique agent identifier" },
                            agent_role: { type: "string", description: "Role of the executing agent (e.g. developer, investigator)" }
                        },
                        required: ["task_id"]
                    }
                },
                {
                    name: "record_assertion",
                    description: "Record a structured technical decision, learning, or observation during the agent's work.",
                    inputSchema: {
                        type: "object",
                        properties: {
                            subject_text: { type: "string", description: "Subject of the assertion (e.g., user, system, database)" },
                            predicate: { type: "string", description: "Relationship/action (e.g., prefers, uses, configures)" },
                            object_text: { type: "string", description: "Object of the assertion (e.g., PostgreSQL, dark mode)" },
                            confidence: { type: "number", description: "Confidence score between 0.0 and 1.0", default: 1.0 }
                        },
                        required: ["subject_text", "predicate", "object_text"]
                    }
                },
                {
                    name: "checkpoint_state",
                    description: "Checkpoint the current progress of the agent (e.g. read files, cursor position) for fault tolerance and crash recovery.",
                    inputSchema: {
                        type: "object",
                        properties: {
                            state_dump: { type: "object", description: "JSON state representation to checkpoint" }
                        },
                        required: ["state_dump"]
                    }
                }
            ]
        };
    } catch (error) {
        console.error("Failed to list tools:", error);
        return { tools: [] };
    }
});

// Proxy Tool Execution
server.setRequestHandler(CallToolRequestSchema, async (request) => {
    try {
        const headers = {
            "Content-Type": "application/json"
        };
        if (API_KEY) headers["Authorization"] = `Bearer ${API_KEY}`;

        if (request.params.name === "add_memory") {
            const endpoint = `${CONDENSATE_URL}/api/v1/episodic`;
            const payload = {
                text: request.params.arguments.text,
                source: request.params.arguments.source || "mcp_bridge",
                project_id: request.params.arguments.project_id || "default",
                metadata: { client: "mcp-bridge" }
            };

            const response = await axios.post(endpoint, payload, { headers });
            return {
                content: [{ type: "text", text: `Memory added. ID: ${response.data.id}` }]
            };
        }

        if (request.params.name === "retrieve_memory") {
            const endpoint = `${CONDENSATE_URL}/api/v1/memory/retrieve`;
            const payload = {
                query: request.params.arguments.query
            };

            const response = await axios.post(endpoint, payload, { headers });
            return {
                content: [{ type: "text", text: response.data.answer }]
            };
        }

        if (request.params.name === "start_task_session") {
            const { task_id, agent_id, agent_role } = request.params.arguments;
            const episodicEndpoint = `${CONDENSATE_URL}/api/v1/episodic`;
            
            // 1. Log start lifecycle event
            await axios.post(episodicEndpoint, {
                text: `Lifecycle Start: Task ${task_id} started by agent ${agent_id || 'unknown'} (${agent_role || 'developer'})`,
                source: "mcp_bridge",
                project_id: "default",
                metadata: {
                    event_type: "lifecycle_start",
                    task_id,
                    agent_id,
                    agent_role
                }
            }, { headers });

            // 2. Query initial context / policies
            const retrieveEndpoint = `${CONDENSATE_URL}/api/v1/memory/retrieve`;
            const response = await axios.post(retrieveEndpoint, {
                query: `What is the context, memories, and policies for task ${task_id}?`
            }, { headers });

            return {
                content: [
                    { type: "text", text: `Task session started for ${task_id}. Initial Context:\n\n${response.data.answer}` }
                ]
            };
        }

        if (request.params.name === "record_assertion") {
            const { subject_text, predicate, object_text, confidence } = request.params.arguments;
            const endpoint = `${CONDENSATE_URL}/api/v1/episodic`;
            
            const payload = {
                text: `Record assertion: ${subject_text} ${predicate} ${object_text}`,
                source: "mcp_bridge",
                project_id: "default",
                metadata: {
                    event_type: "record_assertion",
                    subject_text,
                    predicate,
                    object_text,
                    confidence: confidence !== undefined ? confidence : 1.0
                }
            };

            const response = await axios.post(endpoint, payload, { headers });
            return {
                content: [{ type: "text", text: `Structured assertion recorded. ID: ${response.data.id}` }]
            };
        }

        if (request.params.name === "checkpoint_state") {
            const { state_dump } = request.params.arguments;
            const endpoint = `${CONDENSATE_URL}/api/v1/episodic`;
            
            const payload = {
                text: `Checkpointing execution state`,
                source: "mcp_bridge",
                project_id: "default",
                metadata: {
                    event_type: "checkpoint_state",
                    state_dump
                }
            };

            const response = await axios.post(endpoint, payload, { headers });
            return {
                content: [{ type: "text", text: `Checkpoint created. ID: ${response.data.id}` }]
            };
        }

        throw new Error(`Unknown tool: ${request.params.name}`);
    } catch (error) {
        return {
            content: [{ type: "text", text: `Error: ${error.message}` }],
            isError: true,
        };
    }
});

const transport = new StdioServerTransport();
await server.connect(transport);
