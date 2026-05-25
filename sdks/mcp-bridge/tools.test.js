import { test, describe } from "node:test";
import assert from "node:assert/strict";
import {
    BRIDGE_ONLY_TOOLS,
    fetchServerTools,
    mapToServerTool,
    mergeToolCatalog,
    proxyServerToolCall,
} from "./tools.js";

describe("mergeToolCatalog", () => {
    test("merges bridge tools not present on server", () => {
        const server = [{ name: "store_memory", description: "x", inputSchema: {} }];
        const merged = mergeToolCatalog(server, BRIDGE_ONLY_TOOLS);
        const names = merged.map((t) => t.name);
        assert.ok(names.includes("store_memory"));
        assert.ok(names.includes("retrieve_memory"));
        assert.equal(names.filter((n) => n === "store_memory").length, 1);
    });
});

describe("mapToServerTool", () => {
    test("maps add_memory to store_memory", () => {
        const mapped = mapToServerTool("add_memory", { text: "hello", source: "chat" });
        assert.equal(mapped.name, "store_memory");
        assert.equal(mapped.arguments.content, "hello");
    });
});

describe("fetchServerTools", () => {
    test("fetches catalog from HTTP server", async () => {
        const axios = {
            get: async (url) => {
                assert.equal(url, "http://api.test/mcp/tools");
                return { data: [{ name: "query_graph", inputSchema: {} }] };
            },
        };
        const tools = await fetchServerTools(axios, "http://api.test", "key");
        assert.equal(tools.length, 1);
        assert.equal(tools[0].name, "query_graph");
    });
});

describe("proxyServerToolCall", () => {
    test("posts to /mcp/tools/call", async () => {
        const calls = [];
        const axios = {
            post: async (url, body) => {
                calls.push({ url, body });
                return { data: { content: [{ type: "text", text: "ok" }] } };
            },
        };
        const result = await proxyServerToolCall(
            "store_memory",
            { content: "hi" },
            { axios, condensateUrl: "http://api.test", apiKey: "k" }
        );
        assert.equal(result.content[0].text, "ok");
        assert.equal(calls[0].url, "http://api.test/mcp/tools/call");
        assert.equal(calls[0].body.name, "store_memory");
    });
});
