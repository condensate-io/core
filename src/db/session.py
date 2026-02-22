from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sqlalchemy as sa
import os
from .models import Base

# Database URL from environment or default to local docker
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://condensate:password@localhost:5432/condensate_db")

engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=30,
    pool_timeout=30,
    pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """
    Initialize the database tables and apply incremental schema migrations.

    create_all() only creates tables that don't exist yet — it will NOT add
    new columns to existing tables.  The _apply_migrations() call below runs
    idempotent ALTER TABLE … ADD COLUMN IF NOT EXISTS statements so that any
    columns added to the SQLAlchemy models after the initial table creation are
    automatically present on startup (including after a compose rebuild against
    a persistent volume).
    """
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
