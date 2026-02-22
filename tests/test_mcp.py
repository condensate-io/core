import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from main import app
from src.db.models import ApiKey, Project
import uuid

client = TestClient(app)

def test_mcp_list_tools(db_session, project):
    # Public endpoint
    response = client.get("/mcp/tools")
    assert response.status_code == 200
    tools = response.json()
    assert isinstance(tools, list)
    assert any(t['name'] == 'store_memory' for t in tools)

def test_mcp_tool_call_store_memory(db_session, project):
    # Setup API Key in mock DB
    key_str = f"sk-{uuid.uuid4()}"
    api_key_mock = MagicMock()
    api_key_mock.key = key_str
    api_key_mock.project_id = project.id
    api_key_mock.is_active = True

    # Make db.query(ApiKey) return the mock key
    def mock_query(model):
        q = MagicMock()
        q.filter.return_value.first.return_value = api_key_mock
        return q

    db_session.query.side_effect = mock_query

    # Mock IngressAgent so no real embedding / Qdrant connection is needed
    mock_item = MagicMock()
    mock_item.id = str(uuid.uuid4())

    with patch("src.server.mcp.IngressAgent") as MockIngressAgent, \
         patch("src.server.mcp.BackgroundTasks") as _:
        mock_agent_instance = MagicMock()
        mock_agent_instance.process_memory.return_value = mock_item
        MockIngressAgent.return_value = mock_agent_instance

        payload = {
            "name": "store_memory",
            "arguments": {
                "content": "Test memory content",
                "type": "episodic"
            }
        }

        response = client.post(
            "/mcp/tools/call",
            json=payload,
            headers={"Authorization": f"Bearer {key_str}"}
        )

    assert response.status_code == 200
    assert "Episodic Item stored" in response.json()["content"][0]["text"]

@pytest.fixture(autouse=True)
def override_dependency(db_session):
    from src.db.session import get_db, get_qdrant
    mock_qdrant = MagicMock()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_qdrant] = lambda: mock_qdrant
    yield
    app.dependency_overrides = {}
