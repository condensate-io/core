from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.db.session import get_db, get_qdrant
from src.server.health import router


@pytest.fixture
def health_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_healthz_ok(health_client):
    mock_db = MagicMock()
    mock_qdrant = MagicMock()

    def override_db():
        yield mock_db

    def override_qdrant():
        yield mock_qdrant

    health_client.app.dependency_overrides[get_db] = override_db
    health_client.app.dependency_overrides[get_qdrant] = override_qdrant

    response = health_client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["postgres"] == "ok"
    assert body["checks"]["qdrant"] == "ok"

    health_client.app.dependency_overrides.clear()


def test_health_alias_ok(health_client):
    mock_db = MagicMock()
    mock_qdrant = MagicMock()

    def override_db():
        yield mock_db

    def override_qdrant():
        yield mock_qdrant

    health_client.app.dependency_overrides[get_db] = override_db
    health_client.app.dependency_overrides[get_qdrant] = override_qdrant

    response = health_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    health_client.app.dependency_overrides.clear()


def test_healthz_degraded_when_postgres_fails(health_client):
    mock_db = MagicMock()
    mock_db.execute.side_effect = RuntimeError("connection refused")
    mock_qdrant = MagicMock()

    def override_db():
        yield mock_db

    def override_qdrant():
        yield mock_qdrant

    health_client.app.dependency_overrides[get_db] = override_db
    health_client.app.dependency_overrides[get_qdrant] = override_qdrant

    response = health_client.get("/healthz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert "connection refused" in body["checks"]["postgres"]

    health_client.app.dependency_overrides.clear()
