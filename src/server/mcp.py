import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from qdrant_client import QdrantClient
from sqlalchemy.orm import Session
from src.agents.ingress import IngressAgent
from src.db.models import ApiKey
from src.db.schemas import EpisodicItemCreate
from src.db.session import get_db, get_qdrant
from src.server.admin import get_api_key

logger = logging.getLogger("MCPServer")
mcp_router = APIRouter()


class ToolCall(BaseModel):
    name: str
    arguments: Dict[str, Any]
    id: Optional[str] = None


# ...


@mcp_router.post("/tools/call")
async def call_tool(
    call: ToolCall,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key),
    qdrant_client: QdrantClient = Depends(get_qdrant),
):
    """
    Execute a tool call.
    """
    if call.name == "store_memory":
        try:
            # Prefer project_id from arguments for multi-project simulations
            target_project_id = call.arguments.get("project_id") or str(api_key.project_id)
            agent = IngressAgent(db, qdrant_client)

            item_data = EpisodicItemCreate(
                project_id=target_project_id,
                text=call.arguments.get("content"),
                source="api",  # MCP calls are API sources
                metadata={
                    "type": call.arguments.get("type", "episodic"),
                    "mcp_metadata": call.arguments.get("metadata", {}),
                },
            )
            # 1. Store only (Fast)
            new_item = agent.process_memory(item_data)

            # 2. Schedule Condensation (Background)
            background_tasks.add_task(run_async_condensation, str(target_project_id), str(new_item.id))

            return {
                "content": [
                    {"type": "text", "text": f"Episodic Item stored with ID: {new_item.id}. Condensation queued."}
                ]
            }
        except Exception as e:
            logger.error(f"Error in store_memory: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    elif call.name == "add_data_source":
        # logic similar to admin.create_source
        from src.db.models import DataSource
        from src.engine.scheduler import schedule_data_source

        project_id = api_key.project_id
        ds = DataSource(
            project_id=project_id,
            name=call.arguments.get("name"),
            source_type=call.arguments.get("source_type"),
            configuration=call.arguments.get("configuration", {}),
            cron_schedule=call.arguments.get("cron_schedule"),
            enabled=True,
        )
        db.add(ds)
        db.commit()
        schedule_data_source(ds)
        return {"content": [{"type": "text", "text": f"Data Source created with ID: {ds.id}"}]}

    elif call.name == "trigger_data_source":
        from src.engine.scheduler import trigger_data_source

        try:
            sid = uuid.UUID(call.arguments.get("source_id"))
            trigger_data_source(sid)
            return {"content": [{"type": "text", "text": f"Triggered job for source {sid}"}]}
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Source UUID")

    elif call.name == "query_graph":
        from sqlalchemy import or_, select
        from src.db.models import Assertion, Entity

        project_id = api_key.project_id
        query = call.arguments.get("query", "")
        limit = call.arguments.get("limit", 50)

        # Search Entities
        entity_stmt = (
            select(Entity)
            .where(
                Entity.project_id == project_id,
                or_(Entity.canonical_name.ilike(f"%{query}%"), Entity.type.ilike(f"%{query}%")),
            )
            .limit(limit)
        )
        entities = db.execute(entity_stmt).scalars().all()

        # Search Assertions
        assertion_stmt = (
            select(Assertion)
            .where(
                Assertion.project_id == project_id,
                or_(
                    Assertion.subject_text.ilike(f"%{query}%"),
                    Assertion.predicate.ilike(f"%{query}%"),
                    Assertion.object_text.ilike(f"%{query}%"),
                ),
            )
            .limit(limit)
        )
        assertions = db.execute(assertion_stmt).scalars().all()

        result_text = f"Causal Graph Query Results for '{query}':\n\n"

        result_text += "--- Entities discovered ---\n"
        if not entities:
            result_text += "No matching entities found.\n"
        for e in entities:
            result_text += f"- [{e.type}] {e.canonical_name} (Confidence: {e.confidence})\n"

        result_text += "\n--- Assertions discovered ---\n"
        if not assertions:
            result_text += "No matching assertions found.\n"
        for a in assertions:
            result_text += f"- {a.subject_text} -> {a.predicate} -> {a.object_text} (Status: {a.status}, Confidence: {a.confidence})\n"

        return {"content": [{"type": "text", "text": result_text}]}

    elif call.name == "get_context_analytics":
        from src.engine.analytics import GraphAnalyst

        project_id = api_key.project_id
        limit = call.arguments.get("limit", 20)

        try:
            analyst = GraphAnalyst(db, project_id)
            centrality = analyst.get_centrality()[:limit]
            communities = analyst.get_communities()
            bottlenecks = analyst.get_bottlenecks()

            result_text = "Context Optimization Graph Analytics:\n\n"

            result_text += "--- Top Hebbian Centrality Nodes (Strongest Pathways) ---\n"
            if not centrality:
                result_text += "No reinforced pathways calculated yet.\n"
            for node in centrality:
                result_text += f"- Node: {node.get('label', node.get('id'))} (Score: {node.get('score', 0):.4f})\n"

            result_text += "\n--- Louvain Communities (Consolidated Semantic Subgraphs) ---\n"
            if not communities:
                result_text += "No communities calculated yet.\n"
            for comm in communities[:5]:  # show first 5 clusters
                result_text += f"- Cluster #{comm.get('community_id')}: {', '.join(comm.get('nodes', [])[:10])}\n"

            result_text += "\n--- Graph Bottlenecks (High Attention-Risk Nodes) ---\n"
            if not bottlenecks:
                result_text += "No bottlenecks found.\n"
            for b in bottlenecks[:10]:
                result_text += f"- {b.get('label', b.get('id'))} (Betweenness: {b.get('score', 0):.4f})\n"

            return {"content": [{"type": "text", "text": result_text}]}
        except Exception as e:
            logger.error(f"Error in get_context_analytics: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=404, detail=f"Tool {call.name} not found")


@mcp_router.get("/tools")
def list_tools():
    """List available tools for MCP."""
    return [
        {
            "name": "store_memory",
            "description": "Store an episodic memory",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "type": {"type": "string", "enum": ["episodic", "semantic"]},
                },
                "required": ["content"],
            },
        },
        {
            "name": "add_data_source",
            "description": "Add a new data source (web URLs, files, or local codebase repositories)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "source_type": {"type": "string", "enum": ["url", "file", "api", "codebase"]},
                    "configuration": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Absolute directory path for codebase ingestion"},
                            "max_file_size": {
                                "type": "integer",
                                "description": "Ceiling file size in bytes (default 64KB)",
                            },
                            "allowed_extensions": {"type": "array", "items": {"type": "string"}},
                            "ignore_patterns": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
                "required": ["name", "source_type"],
            },
        },
        {
            "name": "trigger_data_source",
            "description": "Manually trigger a data source ingestion",
            "inputSchema": {
                "type": "object",
                "properties": {"source_id": {"type": "string"}},
                "required": ["source_id"],
            },
        },
        {
            "name": "query_graph",
            "description": "Search the causal memory graph for verified entities, relations, and semantic assertions",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Term to search for within entity names or assertion statements",
                    },
                    "limit": {"type": "integer", "description": "Maximum number of results to return (default 50)"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "get_context_analytics",
            "description": "Get Hebbian path centralities, consolidated Louvain communities, and code graph bottlenecks for token context optimization",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max number of central nodes to retrieve (default 20)"}
                },
            },
        },
    ]


@mcp_router.get("/")
def mcp_root():
    return {"status": "MCP Server Running", "version": "1.0.0"}


def run_async_condensation(project_id: str, item_id: str):
    """
    Background task to run condensation.

    Uses TWO short-lived sessions to avoid holding a DB connection open
    during the entire (long-running) condensation process:
      1. A quick fetch session to load the EpisodicItem (released immediately).
      2. A fresh session passed to the Condenser for its DB writes.

    This ensures we only occupy a connection from the pool when we are
    actually talking to the database, not while waiting for NER or
    CPU-bound guardrail processing.
    """
    import asyncio
    import uuid
    from datetime import datetime, timezone

    from src.db.models import EpisodicItem
    from src.db.session import SessionLocal
    from src.engine.condenser import Condenser
    from src.engine.job_history import log_job as _log_job

    job_id = f"condense_{item_id[:8]}"
    started = datetime.now(timezone.utc)
    _log_job(job_id, f"Condensation [{item_id[:8]}]", "running", started)

    item_obj = None

    # --- Session 1: fetch only, released immediately ---
    fetch_db = SessionLocal()
    try:
        item_obj = fetch_db.query(EpisodicItem).filter(EpisodicItem.id == uuid.UUID(item_id)).first()
        if item_obj is None:
            logger.warning(f"Item {item_id} not found, skipping condensation.")
            return
        # Expunge so we can use the object after the session closes
        fetch_db.expunge(item_obj)
    except Exception as e:
        logger.error(f"Failed to fetch item {item_id}: {e}")
        return
    finally:
        fetch_db.close()  # ← connection returned to pool here

    # --- Session 2: condensation writes (opened after NER+CPU finishes inside) ---
    condense_db = SessionLocal()
    try:
        condenser = Condenser(condense_db)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(condenser.distill(uuid.UUID(project_id), [item_obj]))
        loop.close()
        finished = datetime.now(timezone.utc)
        duration = int((finished - started).total_seconds() * 1000)
        _log_job(job_id, f"Condensation [{item_id[:8]}]", "success", started, finished, duration)
    except Exception as e:
        finished = datetime.now(timezone.utc)
        duration = int((finished - started).total_seconds() * 1000)
        _log_job(job_id, f"Condensation [{item_id[:8]}]", "error", started, finished, duration, str(e))
        logger.error(f"Background condensation failed for item {item_id}: {e}")
    finally:
        condense_db.close()  # ← connection returned to pool here
