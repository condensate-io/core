"""
Tenant isolation and cascade deletion tests.

Fully mocked — no real database or Qdrant connections required.
Works in CI without any external services.
"""
import pytest
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from src.db.models import Project, ApiKey, EpisodicItem, Entity


@asynccontextmanager
async def _noop_lifespan(app: FastAPI):
    """Replacement lifespan that skips all init (DB, Qdrant, NER, etc.)."""
    yield


def _make_app():
    """
    Import the real app and swap its lifespan to the no-op version
    so TestClient never triggers init_db / Qdrant / NER warmup.
    """
    from main import app
    app.router.lifespan_context = _noop_lifespan
    return app


def test_tenant_isolation_and_cascade():
    """
    Verifies:
      1. Ingestion is scoped to the caller's API-key project.
      2. Retrieval routes through the caller's project_id, not a global scope.
      3. Project deletion triggers Qdrant cascade purges for both collections.
    """
    # --- Setup: two projects and API keys ---
    p1_id = uuid.uuid4()
    p2_id = uuid.uuid4()

    ak1 = MagicMock(spec=ApiKey)
    ak1.key = f"sk-test-a-{uuid.uuid4()}"
    ak1.project_id = p1_id
    ak1.is_active = True

    ak2 = MagicMock(spec=ApiKey)
    ak2.key = f"sk-test-b-{uuid.uuid4()}"
    ak2.project_id = p2_id
    ak2.is_active = True

    # --- Build mock DB session ---
    mock_db = MagicMock()
    mock_qdrant = MagicMock()

    def mock_get_db():
        yield mock_db

    def mock_get_qdrant():
        yield mock_qdrant

    app = _make_app()

    from src.db.session import get_db, get_qdrant
    from src.server.admin import get_api_key
    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_qdrant] = mock_get_qdrant

    client = TestClient(app)

    try:
        # ---- 1. Test scoped ingestion via Key A ----
        app.dependency_overrides[get_api_key] = lambda: ak1

        with patch("src.server.v1_api.IngressAgent") as mock_ingress_cls, \
             patch("src.server.v1_api._condense_project_background") as mock_bg:
            mock_ingress = MagicMock()
            mock_item = MagicMock(spec=EpisodicItem)
            mock_item.id = uuid.uuid4()
            mock_item.project_id = p1_id
            mock_ingress.process_memory.return_value = mock_item
            mock_ingress_cls.return_value = mock_ingress

            resp = client.post(
                "/api/v1/episodic",
                json={
                    "project_id": str(p1_id),
                    "text": "Secret project details A",
                    "source": "api",
                },
                headers={"Authorization": f"Bearer {ak1.key}"},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "stored"

        # ---- 2. Test scoped retrieval: Key B sees project B, Key A sees project A ----
        with patch("src.server.router_api.MemoryRouter") as mock_router_cls:
            mock_mr = MagicMock()

            async def mock_route(project_id, query, **kwargs):
                return {
                    "answer": f"Answer for {project_id}",
                    "sources": [],
                    "strategy": "recall",
                }

            mock_mr.route_and_retrieve = mock_route
            mock_router_cls.return_value = mock_mr

            # Retrieve with Key B → should scope to p2
            app.dependency_overrides[get_api_key] = lambda: ak2
            resp_b = client.post(
                "/api/v1/memory/retrieve",
                json={"query": "Get info"},
                headers={"Authorization": f"Bearer {ak2.key}"},
            )
            assert resp_b.status_code == 200
            assert resp_b.json()["answer"] == f"Answer for {p2_id}"

            # Retrieve with Key A → should scope to p1
            app.dependency_overrides[get_api_key] = lambda: ak1
            resp_a = client.post(
                "/api/v1/memory/retrieve",
                json={"query": "Get info"},
                headers={"Authorization": f"Bearer {ak1.key}"},
            )
            assert resp_a.status_code == 200
            assert resp_a.json()["answer"] == f"Answer for {p1_id}"

        # ---- 3. Test cascade delete ----
        mock_project = MagicMock(spec=Project)
        mock_project.id = p1_id
        mock_project.name = "Project-A"

        mock_db.reset_mock()
        mock_qdrant.reset_mock()

        # Admin delete: project lookup returns the project
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        with patch("src.server.admin.verify_admin", return_value="admin"):
            resp_delete = client.delete(
                f"/api/admin/projects/{p1_id}",
                headers={"Authorization": "Basic YWRtaW46YWRtaW4="},
            )
            assert resp_delete.status_code == 200
            assert resp_delete.json()["status"] == "deleted"

            # Qdrant delete should be called for both collections
            assert mock_qdrant.delete.call_count == 2

    finally:
        app.dependency_overrides.clear()
