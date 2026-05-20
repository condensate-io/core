import pytest
import uuid
from fastapi.testclient import TestClient
from main import app
from unittest.mock import MagicMock, patch
from src.db.session import SessionLocal, get_qdrant
from src.db.models import Project, ApiKey, EpisodicItem, Entity, Assertion, Relation

@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()

def test_tenant_isolation_and_cascade(db):
    # 1. Create two distinct projects and API keys
    p1 = Project(name=f"Project-A-{uuid.uuid4().hex[:6]}")
    p2 = Project(name=f"Project-B-{uuid.uuid4().hex[:6]}")
    db.add_all([p1, p2])
    db.commit()
    db.refresh(p1)
    db.refresh(p2)

    ak1 = ApiKey(key=f"sk-test-a-{uuid.uuid4()}", name="key-a", project_id=p1.id)
    ak2 = ApiKey(key=f"sk-test-b-{uuid.uuid4()}", name="key-b", project_id=p2.id)
    db.add_all([ak1, ak2])
    db.commit()

    # 2. Ingest episodic memory under Project A using API Key A via TestClient
    with patch("main.start_scheduler"), patch("main.init_db"):
        client = TestClient(app)

        # Ingest memory into Project A
        # Since background tasks are run, we mock QdrantClient inside create_episodic_item
        mock_qdrant = MagicMock()
        app.dependency_overrides[get_qdrant] = lambda: mock_qdrant
        
        with patch("src.server.v1_api.IngressAgent") as mock_ingress_class:
            mock_ingress = MagicMock()
            mock_item = EpisodicItem(id=uuid.uuid4(), project_id=p1.id, text="Secret project details A", source="api")
            mock_ingress.process_memory.return_value = mock_item
            mock_ingress_class.return_value = mock_ingress

            headers_a = {"Authorization": f"Bearer {ak1.key}"}
            payload = {
                "project_id": str(p1.id),
                "text": "Secret project details A",
                "source": "api"
            }
            resp = client.post("/api/v1/episodic", json=payload, headers=headers_a)
            assert resp.status_code == 200
            assert resp.json()["status"] == "stored"

            # 3. Verify that retrieve request with Key B cannot retrieve Project A's memory
            with patch("src.server.router_api.MemoryRouter") as mock_router_class:
                mock_mr = MagicMock()
                # route_and_retrieve is an async function
                async def mock_route(project_id, query):
                    return {
                        "answer": f"Answer for {project_id}",
                        "sources": [],
                        "strategy": "recall"
                    }
                mock_mr.route_and_retrieve = mock_route
                mock_router_class.return_value = mock_mr

                # Call retrieve with Key B
                headers_b = {"Authorization": f"Bearer {ak2.key}"}
                resp_retrieve = client.post("/api/v1/memory/retrieve", json={"query": "Get info"}, headers=headers_b)
                assert resp_retrieve.status_code == 200
                assert resp_retrieve.json()["answer"] == f"Answer for {p2.id}"

                # Call retrieve with Key A
                resp_retrieve_a = client.post("/api/v1/memory/retrieve", json={"query": "Get info"}, headers=headers_a)
                assert resp_retrieve_a.status_code == 200
                assert resp_retrieve_a.json()["answer"] == f"Answer for {p1.id}"

    # 4. Verify cascade delete in Qdrant and DB
    # We mock Qdrant inside admin.py to verify it gets deleted from both collections
    mock_qdrant_admin = MagicMock()
    app.dependency_overrides[get_qdrant] = lambda: mock_qdrant_admin

    # We manually insert some entities/assertions under project A to make sure DB cascade works
    e1 = Entity(project_id=p1.id, canonical_name="Target Entity", type="Agent")
    db.add(e1)
    db.commit()
    db.refresh(e1)

    # Trigger project A deletion via admin delete endpoint
    with patch("src.server.admin.verify_admin", return_value="admin"):
        resp_delete = client.delete(
            f"/api/admin/projects/{p1.id}",
            headers={"Authorization": "Basic YWRtaW46YWRtaW4="}
        )
        assert resp_delete.status_code == 200
        assert resp_delete.json()["status"] == "deleted"

        # Assert Qdrant delete was called for project A in episodic_chunks and memories
        assert mock_qdrant_admin.delete.call_count == 2
        
        # Verify Cascade deletion from DB
        db_project = db.query(Project).filter(Project.id == p1.id).first()
        assert db_project is None
        db_entity = db.query(Entity).filter(Entity.project_id == p1.id).first()
        assert db_entity is None

    # Clear overrides at the end
    app.dependency_overrides.clear()
