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
    """
    Initialize the database tables and apply incremental schema migrations.
    """
    # Import all models to register them with Base.metadata
    from . import models
    try:
        from src.synapses import models as synapse_models
    except ImportError:
        pass
        
    Base.metadata.create_all(bind=engine)
    _apply_migrations()


def _apply_migrations():
    """
    Idempotent schema migrations applied on every startup.
    Each statement uses IF NOT EXISTS / server-side guards so it is safe to
    run repeatedly without error.
    """
    import logging
    log = logging.getLogger("init_db")

    migrations = [
        # --- HITL review fields (hitl_review_001) ---
        "ALTER TABLE assertions ADD COLUMN IF NOT EXISTS reviewed_by VARCHAR",
        "ALTER TABLE assertions ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP",
        "ALTER TABLE assertions ADD COLUMN IF NOT EXISTS rejection_reason VARCHAR",
        "ALTER TABLE assertions ADD COLUMN IF NOT EXISTS instruction_score FLOAT NOT NULL DEFAULT 0.0",
        "ALTER TABLE assertions ADD COLUMN IF NOT EXISTS safety_score FLOAT NOT NULL DEFAULT 0.0",
        # status column default update (safe to run even if already set)
        "ALTER TABLE assertions ALTER COLUMN status SET DEFAULT 'pending_review'",
        # index (CREATE INDEX IF NOT EXISTS is supported in Postgres 9.5+)
        "CREATE INDEX IF NOT EXISTS ix_assertions_status ON assertions (status)",
        # --- OmniSim Temporal Tracking (Phase 1) ---
        "ALTER TABLE assertions ADD COLUMN IF NOT EXISTS temporal_step INTEGER",
        "ALTER TABLE assertions ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb",
        "ALTER TABLE relations ADD COLUMN IF NOT EXISTS temporal_start INTEGER",
        "ALTER TABLE relations ADD COLUMN IF NOT EXISTS temporal_end INTEGER",
        "ALTER TABLE relations ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb",
        # --- FK CASCADE / SET NULL (fk_001) ---
        """
        DO $$ 
        BEGIN 
            IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'assertions_subject_entity_id_fkey') THEN 
                ALTER TABLE assertions DROP CONSTRAINT assertions_subject_entity_id_fkey; 
            END IF; 
            ALTER TABLE assertions ADD CONSTRAINT assertions_subject_entity_id_fkey FOREIGN KEY (subject_entity_id) REFERENCES entities(id) ON DELETE SET NULL;

            IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'assertions_object_entity_id_fkey') THEN 
                ALTER TABLE assertions DROP CONSTRAINT assertions_object_entity_id_fkey; 
            END IF; 
            ALTER TABLE assertions ADD CONSTRAINT assertions_object_entity_id_fkey FOREIGN KEY (object_entity_id) REFERENCES entities(id) ON DELETE SET NULL;
        END $$;
        """
    ]

    with engine.connect() as conn:
        for stmt in migrations:
            try:
                conn.execute(sa.text(stmt))
                conn.commit()
            except Exception as exc:
                conn.rollback()
                log.warning("Migration statement skipped (%s): %s", exc, stmt)

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
