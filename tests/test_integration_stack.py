"""
Integration stack tests (PostgreSQL + Qdrant)
==============================================

Verifies that the live infrastructure services required by Condensate are
reachable and that Postgres has Alembic-managed schema tables present.

These tests are marked ``integration`` and are skipped automatically when
Postgres or Qdrant are unreachable (e.g. during offline unit-test runs).

Run via Docker (recommended):

    wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && docker compose up -d condensate-db condensate-vector && docker compose run --rm condensate-core pytest tests/test_integration_stack.py -v -m integration"

Run locally when services are already up:

    alembic upgrade head
    pytest tests/test_integration_stack.py -v -m integration
"""

from __future__ import annotations

import os

import httpx
import pytest
import sqlalchemy as sa
from qdrant_client import QdrantClient
from sqlalchemy import inspect as sa_inspect

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@condensate-db:5432/condensate",
)

QDRANT_HOST = os.getenv("QDRANT_HOST", "condensate-vector")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_URL = os.getenv("QDRANT_URL", f"http://{QDRANT_HOST}:{QDRANT_PORT}")

API_BASE_URL = os.getenv("API_BASE_URL", "http://condensate-core:8000")

ALEMBIC_TABLES = ("projects", "entities")


def _db_reachable() -> bool:
    try:
        engine = sa.create_engine(DATABASE_URL, connect_args={"connect_timeout": 3})
        with engine.connect():
            pass
        engine.dispose()
        return True
    except Exception:
        return False


def _qdrant_reachable() -> bool:
    try:
        client = QdrantClient(url=QDRANT_URL, timeout=3)
        client.get_collections()
        client.close()
        return True
    except Exception:
        return False


def _api_reachable() -> bool:
    try:
        with httpx.Client(timeout=3.0) as client:
            response = client.get(f"{API_BASE_URL}/healthz")
            return response.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.integration

requires_db = pytest.mark.skipif(
    not _db_reachable(),
    reason="Live Postgres not reachable — skipping integration DB tests",
)

requires_qdrant = pytest.mark.skipif(
    not _qdrant_reachable(),
    reason="Live Qdrant not reachable — skipping integration vector tests",
)


@pytest.fixture(scope="module", autouse=True)
def ensure_migrations_applied():
    """Apply Alembic migrations so schema table checks reflect head revision."""
    if not _db_reachable():
        yield
        return

    from alembic import command
    from alembic.config import Config

    command.upgrade(Config("alembic.ini"), "head")
    yield


@pytest.fixture(scope="module")
def db_engine():
    engine = sa.create_engine(DATABASE_URL)
    yield engine
    engine.dispose()


@requires_db
def test_postgres_connects(db_engine):
    with db_engine.connect() as conn:
        result = conn.execute(sa.text("SELECT 1")).scalar()
    assert result == 1


@requires_db
@pytest.mark.parametrize("table_name", ALEMBIC_TABLES)
def test_postgres_alembic_tables_exist(db_engine, table_name):
    inspector = sa_inspect(db_engine)
    tables = inspector.get_table_names()
    assert table_name in tables, (
        f"Table '{table_name}' not found in Postgres. Run `alembic upgrade head`."
    )


@requires_qdrant
def test_qdrant_collections_list():
    client = QdrantClient(url=QDRANT_URL, timeout=5)
    try:
        collections = client.get_collections()
        assert collections is not None
    finally:
        client.close()


@pytest.mark.skipif(
    not _api_reachable(),
    reason="API not reachable — skipping optional /healthz integration check",
)
def test_api_healthz_when_reachable():
    with httpx.Client(timeout=5.0) as client:
        response = client.get(f"{API_BASE_URL}/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["postgres"] == "ok"
    assert body["checks"]["qdrant"] == "ok"
