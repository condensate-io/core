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
import { executeToolCall } from "./handlers.js";
import {
    BRIDGE_ONLY_TOOLS,
    SERVER_PROXY_TOOL_NAMES,
    fetchServerTools,
    mapToServerTool,
    mergeToolCatalog,
    proxyServerToolCall,
} from "./tools.js";

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

// Proxy Tool Listing — merge HTTP server catalog with bridge-only tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
    try {
        let serverTools = [];
        try {
            serverTools = await fetchServerTools(axios, CONDENSATE_URL, API_KEY);
        } catch (error) {
            console.error("Could not fetch /mcp/tools from server, using bridge-only catalog:", error.message);
        }
        return { tools: mergeToolCatalog(serverTools, BRIDGE_ONLY_TOOLS) };
    } catch (error) {
        console.error("Failed to list tools:", error);
        return { tools: BRIDGE_ONLY_TOOLS };
    }
});

// Proxy Tool Execution
server.setRequestHandler(CallToolRequestSchema, async (request) => {
    try {
        const deps = {
            axios,
            condensateUrl: CONDENSATE_URL,
            apiKey: API_KEY,
        };
        const toolName = request.params.name;
        const args = request.params.arguments ?? {};

        if (toolName === "add_memory" || SERVER_PROXY_TOOL_NAMES.has(toolName)) {
            const mapped = mapToServerTool(toolName, args);
            return await proxyServerToolCall(mapped.name, mapped.arguments, deps);
        }

        return await executeToolCall(toolName, args, deps);
    } catch (error) {
        return {
            content: [{ type: "text", text: `Error: ${error.message}` }],
            isError: true,
        };
    }
});

const transport = new StdioServerTransport();
await server.connect(transport);
