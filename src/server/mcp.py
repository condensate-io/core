from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import logging

from src.db.session import get_db, get_qdrant
from src.server.admin import get_api_key
from src.db.models import ApiKey
from src.agents.ingress import IngressAgent
from src.db.schemas import EpisodicItemCreate
from qdrant_client import QdrantClient
import os
import uuid

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
    qdrant_client: QdrantClient = Depends(get_qdrant)
):
    """
    Execute a tool call.
    """
    if call.name == "store_memory":
        try:
            agent = IngressAgent(db, qdrant_client)
            # Map tool arguments to EpisodicItemCreate
            item_data = EpisodicItemCreate(
                project_id=str(api_key.project_id),
                text=call.arguments.get("content"),
                source="api", # MCP calls are API sources
                metadata={
                    "type": call.arguments.get("type", "episodic"), 
                    "mcp_metadata": call.arguments.get("metadata", {})
                }
            )
            # 1. Store only (Fast)
            new_item = agent.process_memory(item_data)
            
            # 2. Schedule Condensation (Background)
            background_tasks.add_task(run_async_condensation, str(api_key.project_id), str(new_item.id))
            
            return {"content": [{"type": "text", "text": f"Episodic Item stored with ID: {new_item.id}. Condensation queued."}]}
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
            enabled=True
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
                    "type": {"type": "string", "enum": ["episodic", "semantic"]}
                },
                "required": ["content"]
            }
        },
        {
            "name": "add_data_source",
            "description": "Add a new data source",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "source_type": {"type": "string", "enum": ["url", "file", "api"]},
                    "configuration": {"type": "object"}
                },
                "required": ["name", "source_type"]
            }
        },
        {
            "name": "trigger_data_source",
            "description": "Manually trigger a data source ingestion",
            "inputSchema": {
                "type": "object",
                "properties": {
                   "source_id": {"type": "string"}
                },
                "required": ["source_id"]
            }
        }
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
    from src.db.session import SessionLocal
    from src.db.models import EpisodicItem
    from src.engine.condenser import Condenser
    from src.engine.scheduler import _log_job
    from datetime import datetime, timezone
    import uuid
    import asyncio

    job_id = f"condense_{item_id[:8]}"
    started = datetime.now(timezone.utc)
    _log_job(job_id, f"Condensation [{item_id[:8]}]", "running", started)

    item_text = None
    item_obj = None

    # --- Session 1: fetch only, released immediately ---
    fetch_db = SessionLocal()
    try:
        item_obj = fetch_db.query(EpisodicItem).filter(
            EpisodicItem.id == uuid.UUID(item_id)
        ).first()
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
