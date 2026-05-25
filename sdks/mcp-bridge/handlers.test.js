import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { buildRequestHeaders, executeToolCall } from "./handlers.js";

describe("buildRequestHeaders", () => {
    test("includes Authorization when apiKey is set", () => {
        const h = buildRequestHeaders("secret");
        assert.equal(h["Content-Type"], "application/json");
        assert.equal(h["Authorization"], "Bearer secret");
    });

    test("omits Authorization when apiKey is missing", () => {
        const h = buildRequestHeaders(undefined);
        assert.equal(h["Content-Type"], "application/json");
        assert.equal("Authorization" in h, false);
    });
});

describe("add_memory", () => {
    test("success returns memory id", async () => {
        const calls = [];
        const axios = {
            post: async (url, payload, opts) => {
                calls.push({ url, payload, opts });
                return { data: { id: "mem-1" } };
            },
        };
        const result = await executeToolCall(
            "add_memory",
            { text: "hello", source: "test", project_id: "p1" },
            { axios, condensateUrl: "http://api.test", apiKey: "k" }
        );
        assert.equal(result.content[0].text, "Memory added. ID: mem-1");
        assert.equal(calls.length, 1);
        assert.equal(calls[0].url, "http://api.test/api/v1/episodic");
        assert.deepEqual(calls[0].payload, {
            text: "hello",
            source: "test",
            project_id: "p1",
            metadata: { client: "mcp-bridge" },
        });
        assert.deepEqual(calls[0].opts.headers, {
            "Content-Type": "application/json",
            Authorization: "Bearer k",
        });
    });

    test("applies default source and project_id", async () => {
        const axios = {
            post: async (_url, payload) => {
                assert.equal(payload.source, "mcp_bridge");
                assert.equal(payload.project_id, "default");
                return { data: { id: "x" } };
            },
        };
        await executeToolCall("add_memory", { text: "t" }, { axios, condensateUrl: "http://h", apiKey: undefined });
    });

    test("error propagates from axios", async () => {
        const axios = {
            post: async () => {
                throw new Error("network down");
            },
        };
        await assert.rejects(
            () => executeToolCall("add_memory", { text: "t" }, { axios, condensateUrl: "http://h", apiKey: undefined }),
            { message: "network down" }
        );
    });
});

describe("retrieve_memory", () => {
    test("success returns answer text", async () => {
        const axios = {
            post: async (url, payload, opts) => {
                assert.equal(url, "http://h/api/v1/memory/retrieve");
                assert.deepEqual(payload, { query: "q?" });
                assert.deepEqual(opts.headers, { "Content-Type": "application/json" });
                return { data: { answer: "the answer" } };
            },
        };
        const result = await executeToolCall("retrieve_memory", { query: "q?" }, { axios, condensateUrl: "http://h", apiKey: undefined });
        assert.equal(result.content[0].text, "the answer");
    });

    test("error propagates from axios", async () => {
        const axios = {
            post: async () => {
                const err = new Error("bad request");
                throw err;
            },
        };
        await assert.rejects(
            () => executeToolCall("retrieve_memory", { query: "q" }, { axios, condensateUrl: "http://h", apiKey: undefined }),
            { message: "bad request" }
        );
    });
});

describe("record_assertion", () => {
    test("success with default confidence", async () => {
        const axios = {
            post: async (_url, payload) => {
                assert.equal(payload.metadata.confidence, 1.0);
                return { data: { id: "a1" } };
            },
        };
        const result = await executeToolCall(
            "record_assertion",
            { subject_text: "U", predicate: "likes", object_text: "SQL" },
            { axios, condensateUrl: "http://h", apiKey: undefined }
        );
        assert.equal(result.content[0].text, "Structured assertion recorded. ID: a1");
    });

    test("success with explicit confidence", async () => {
        const axios = {
            post: async (_url, payload) => {
                assert.equal(payload.metadata.confidence, 0.5);
                return { data: { id: "a2" } };
            },
        };
        await executeToolCall(
            "record_assertion",
            { subject_text: "U", predicate: "likes", object_text: "SQL", confidence: 0.5 },
            { axios, condensateUrl: "http://h", apiKey: undefined }
        );
    });

    test("error propagates from axios", async () => {
        const axios = {
            post: async () => {
                throw new Error("server error");
            },
        };
        await assert.rejects(
            () =>
                executeToolCall(
                    "record_assertion",
                    { subject_text: "a", predicate: "b", object_text: "c" },
                    { axios, condensateUrl: "http://h", apiKey: undefined }
                ),
            { message: "server error" }
        );
    });
});
