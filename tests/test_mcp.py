import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def _noop_lifespan(app: FastAPI):
    yield

def _make_app():
    from main import app
    app.router.lifespan_context = _noop_lifespan
    return app

client = TestClient(_make_app())

from src.db.models import ApiKey, Project
import uuid

def test_mcp_list_tools(db_session, project):
    # Public endpoint
    response = client.get("/mcp/tools")
    assert response.status_code == 200
    tools = response.json()
    assert isinstance(tools, list)
    assert any(t['name'] == 'store_memory' for t in tools)

def test_mcp_tool_call_store_memory(db_session, project):
    from src.server.admin import get_api_key
    key_str = f"sk-{uuid.uuid4()}"
    api_key_mock = MagicMock()
    api_key_mock.key = key_str
    api_key_mock.project_id = project.id
    api_key_mock.is_active = True
    client.app.dependency_overrides[get_api_key] = lambda: api_key_mock

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

def test_mcp_tool_call_add_data_source(db_session, project):
    from src.server.admin import get_api_key
    key_str = f"sk-{uuid.uuid4()}"
    api_key_mock = MagicMock()
    api_key_mock.key = key_str
    api_key_mock.project_id = project.id
    api_key_mock.is_active = True
    client.app.dependency_overrides[get_api_key] = lambda: api_key_mock

    with patch("src.engine.scheduler.schedule_data_source") as mock_schedule:
        payload = {
            "name": "add_data_source",
            "arguments": {
                "name": "My Codebase Repo",
                "source_type": "codebase",
                "configuration": {
                    "path": "/absolute/path/to/code",
                    "max_file_size": 65536
                }
            }
        }

        response = client.post(
            "/mcp/tools/call",
            json=payload,
            headers={"Authorization": f"Bearer {key_str}"}
        )

    assert response.status_code == 200, response.json()
    assert "Data Source created with ID" in response.json()["content"][0]["text"]
    assert mock_schedule.called

def test_mcp_tool_call_query_graph(db_session, project):
    from src.server.admin import get_api_key
    key_str = f"sk-{uuid.uuid4()}"
    api_key_mock = MagicMock()
    api_key_mock.key = key_str
    api_key_mock.project_id = project.id
    api_key_mock.is_active = True
    client.app.dependency_overrides[get_api_key] = lambda: api_key_mock

    # Mock DB execute scalars
    mock_entity = MagicMock()
    mock_entity.canonical_name = "test_node"
    mock_entity.type = "class"
    mock_entity.confidence = 0.95

    mock_assertion = MagicMock()
    mock_assertion.subject_text = "test_node"
    mock_assertion.predicate = "defines"
    mock_assertion.object_text = "helper_method"
    mock_assertion.status = "verified"
    mock_assertion.confidence = 0.88

    mock_entities_result = MagicMock()
    mock_entities_result.scalars.return_value.all.return_value = [mock_entity]
    
    mock_assertions_result = MagicMock()
    mock_assertions_result.scalars.return_value.all.return_value = [mock_assertion]

    # Side effects for db_session.execute
    db_session.execute.side_effect = [mock_entities_result, mock_assertions_result]

    payload = {
        "name": "query_graph",
        "arguments": {
            "query": "test_node",
            "limit": 10
        }
    }

    response = client.post(
        "/mcp/tools/call",
        json=payload,
        headers={"Authorization": f"Bearer {key_str}"}
    )

    assert response.status_code == 200
    res_text = response.json()["content"][0]["text"]
    assert "Causal Graph Query Results" in res_text
    assert "test_node" in res_text
    assert "defines" in res_text
    assert "helper_method" in res_text

def test_mcp_tool_call_get_context_analytics(db_session, project):
    from src.server.admin import get_api_key
    key_str = f"sk-{uuid.uuid4()}"
    api_key_mock = MagicMock()
    api_key_mock.key = key_str
    api_key_mock.project_id = project.id
    api_key_mock.is_active = True
    client.app.dependency_overrides[get_api_key] = lambda: api_key_mock

    # Mock GraphAnalyst
    mock_analyst = MagicMock()
    mock_analyst.get_centrality.return_value = [
        {"id": "node-1", "label": "MainController", "score": 0.85}
    ]
    mock_analyst.get_communities.return_value = [
        {"community_id": 0, "nodes": ["MainController", "DBService"]}
    ]
    mock_analyst.get_bottlenecks.return_value = [
        {"id": "node-2", "label": "NetworkStack", "score": 0.9}
    ]

    with patch("src.engine.analytics.GraphAnalyst") as MockGraphAnalyst:
        MockGraphAnalyst.return_value = mock_analyst

        payload = {
            "name": "get_context_analytics",
            "arguments": {
                "limit": 5
            }
        }

        response = client.post(
            "/mcp/tools/call",
            json=payload,
            headers={"Authorization": f"Bearer {key_str}"}
        )

    assert response.status_code == 200
    res_text = response.json()["content"][0]["text"]
    assert "Context Optimization Graph Analytics" in res_text
    assert "MainController" in res_text
    assert "Cluster #0" in res_text
    assert "NetworkStack" in res_text

@pytest.fixture(autouse=True)
def override_dependency(db_session):
    from src.db.session import get_db, get_qdrant
    mock_qdrant = MagicMock()
    client.app.dependency_overrides[get_db] = lambda: db_session
    client.app.dependency_overrides[get_qdrant] = lambda: mock_qdrant
    yield
    client.app.dependency_overrides = {}
