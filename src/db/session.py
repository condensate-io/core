from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sqlalchemy as sa
import os
from .models import Base

# Database URL from environment or default to local docker
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://condensate:password@localhost:5432/condensate_db")

import json
import uuid

def _json_serializer(obj):
    if isinstance(obj, uuid.UUID):
        return str(obj)
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

def _pool_kw():
    """Tune QueuePool for concurrent API + MCP + background work (e.g. parallel OmniSim)."""
    return {
        "pool_size": int(os.getenv("SQLALCHEMY_POOL_SIZE", "30")),
        "max_overflow": int(os.getenv("SQLALCHEMY_MAX_OVERFLOW", "50")),
        "pool_timeout": int(os.getenv("SQLALCHEMY_POOL_TIMEOUT", "60")),
        "pool_recycle": int(os.getenv("SQLALCHEMY_POOL_RECYCLE", "1800")),
        "pool_pre_ping": True,
    }

engine = create_engine(
    DATABASE_URL,
    **_pool_kw(),
    json_serializer=lambda obj: json.dumps(obj, default=_json_serializer)
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Apply Alembic migrations on startup. Fails fast if migrations cannot run."""
    # Import all models so Alembic autogenerate sees the full metadata graph.
    from . import models
    try:
        from src.synapses import models as synapse_models
    except ImportError:
        pass

    import logging
    from alembic import command
    from alembic.config import Config

    log = logging.getLogger("init_db")
    log.info("Running database migrations via Alembic...")
    try:
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        log.info("Database migrations completed successfully.")
    except Exception as e:
        log.error("Failed to run database migrations: %s", e, exc_info=True)
        raise RuntimeError(
            "Database migration failed; refusing to start with an unmigrated schema. "
            "Check DATABASE_URL and run `alembic upgrade head` manually."
        ) from e


def get_db():
    """
    Dependency for getting a DB session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from qdrant_client import QdrantClient

# Qdrant URL from environment
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = os.getenv("QDRANT_PORT", "6333")
QDRANT_URL = os.getenv("QDRANT_URL", f"http://{QDRANT_HOST}:{QDRANT_PORT}")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)

def get_qdrant():
    """
    Dependency for Qdrant Client.
    """
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    try:
        yield client
    finally:
        client.close()
