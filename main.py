import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

from src.server.admin import router as admin_router
from src.server.mcp import mcp_router
from src.engine.thread_shard import AdaptiveThreadShard
from src.db.session import init_db

from contextlib import asynccontextmanager

from src.engine.scheduler import start_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    start_scheduler()
    
    # Init Qdrant Collections
    from src.db.session import QDRANT_URL, QDRANT_API_KEY
    from src.db.qdrant import init_qdrant
    from qdrant_client import QdrantClient
    
    try:
        q_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        init_qdrant(q_client)
        q_client.close()
    except Exception as e:
        import logging
        logging.getLogger("Main").error(f"Failed to init Qdrant: {e}")

    # Bootstrap Stop Words corpus (fetch ISO list + cache to disk)
    from src.engine.stopwords import bootstrap_stop_words
    bootstrap_stop_words()

    # Bootstrap LLM
    from src.llm.bootstrap import bootstrap_llm
    import asyncio
    asyncio.create_task(bootstrap_llm()) # Run in background so app starts quickly

    # Warm up NER model — downloads weights and loads into memory before first request
    async def _warmup_ner():
        import logging
        import asyncio
        log = logging.getLogger("NERWarmup")
        try:
            log.info("Warming up ModernBERT NER model...")
            from src.engine.ner import get_ner_engine
            loop = asyncio.get_event_loop()
            # Run blocking model load in a thread so the event loop stays free
            engine = await loop.run_in_executor(None, get_ner_engine)
            # Run a tiny inference to JIT-compile any lazy ops
            await loop.run_in_executor(None, engine.extract_entities, "Warmup: Alice works at Acme Corp.")
            log.info("ModernBERT NER model ready.")
        except Exception as e:
            log.error(f"NER warmup failed (non-fatal): {e}")

    asyncio.create_task(_warmup_ner())

    yield
    # Shutdown logic if needed

# Initialize App
app = FastAPI(title="Condensate Memory System", lifespan=lifespan)

# Include Routers
# Include Routers
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(mcp_router, prefix="/mcp", tags=["mcp"])

from src.server.router_api import router as memory_router
app.include_router(memory_router, prefix="/api/v1", tags=["memory"])

from src.server.v1_api import router as v1_router
app.include_router(v1_router) # already has /v1 prefix

from src.server.ingest_api import router as ingest_router
app.include_router(ingest_router)

from src.server.review_api import router as review_router
app.include_router(review_router)

# Serve Frontend
# Check if frontend build exists
FRONTEND_DIR = os.path.join(os.getcwd(), "frontend", "dist")
if os.path.exists(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")
    
    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
    
    # Catch-all for React Router
    @app.exception_handler(404)
    async def not_found(request: Request, exc):
        if request.url.path.startswith("/api"):
            return {"error": "Not found"}, 404
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
