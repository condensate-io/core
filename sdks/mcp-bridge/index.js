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
        // Fetch tools from Python backend's internal MCP catalog if available
        // Or hardcode the standard tools here to avoid roundtrip latency/complexity during startup
        // Let's hardcode the 'standard' tools for now as they are stable specs.
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
                project_id: request.params.arguments.project_id || "default", // Backend handles UUID generation if needed
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
