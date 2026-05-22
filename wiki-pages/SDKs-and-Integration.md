# SDKs and Integration

Condensate is designed to be the canonical memory substrate for AI agent swarms, and as such, it provides first-class support across multiple languages and ecosystems. Whether you are building an agent in Python, a frontend in TypeScript, or a high-performance system in Rust or Go, Condensate provides native SDKs to seamlessly integrate verified, multi-agent causal memory.

---

## 🐍 Python SDK

The Python SDK is the primary integration path for most agent frameworks (like LangChain, AutoGen, and CrewAI).

### Installation

```bash
pip install condensate
```

### Core Components

- **`CondensateClient`**: The main interface for connecting to the Condensate API, storing episodic memories, and retrieving graph context.
- **`CondensateOrchestrationHooks`**: A suite of decorators and callbacks for hooking Condensate into your agent's lifecycle.

### Quick Example

```python
from condensate import CondensateClient

client = CondensateClient("http://localhost:8000", api_key="sk-your-key")

# Store a memory
client.store_memory(
    content="User requested the system to always prefer dark mode.",
    source="chat"
)

# Retrieve context
context = client.retrieve("What are the user's UI preferences?")
print(context)
```

---

## 🟦 TypeScript SDK

Ideal for building web dashboards, MCP bridges, or agent frontends in Node.js, Next.js, and Vercel.

### Installation

```bash
npm install @condensate-io/sdk
```

---

## 🦀 Rust SDK

For high-performance, concurrent, and systems-level memory management.

### Installation

```bash
cargo add condensate
```

---

## 🐹 Go SDK

For building scalable microservices and orchestration layers.

### Installation

```bash
go get github.com/condensate-io/condensate-go-sdk
```

---

## 🌉 MCP Bridge Integration

Condensate natively supports the **Model Context Protocol (MCP)**. This allows seamless integration with agent hosts like Claude Desktop, Cursor, and Windsurf without needing to write custom API clients.

The MCP Bridge acts as a universal adapter, exposing Condensate's [[Architecture|Merkle-DAGs]] and [[Synapse-Engine|Synapse Engine]] as standard tools to any compatible LLM environment.

```bash
npx -y @condensate/core
```

---

## 🔄 Agent Lifecycle Hooks

To maintain causal integrity across multi-agent workflows (such as those orchestrated by Symphony or AutoGen), the Condensate SDK provides standard **Lifecycle Hooks**. These ensure that agent state transitions are properly recorded in the memory graph, preventing [[The-Problem#lost-causality|Lost Causality]].

You can wire these up to your agent framework of choice:

- `on_agent_started`: Fires when an agent begins a task. Initializes a new temporal context node.
- `on_agent_suspended`: Fires when an agent waits for Human-in-the-Loop (HITL) input or an external API.
- `on_agent_resumed`: Fires when the agent resumes execution.
- `on_agent_crashed`: Records stack traces and failure modes directly into the memory graph for future debugging and retrieval.
- `on_agent_completed`: Consolidates the agent's scratchpad into canonical knowledge.

### Symphony-like Orchestration Support

Condensate hooks are designed to map directly onto Symphony-like orchestration paradigms. By attaching Condensate to your orchestrator's event bus, you instantly grant all child agents a shared, synchronized memory layer powered by CRDTs.

---

**Next Steps**: Check out the [[Getting-Started]] guide to spin up your own instance.
