import os

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from src.retrieve.router import MemoryRouter

@pytest.mark.asyncio
async def test_router_classification(monkeypatch):
    monkeypatch.setenv("RETRIEVE_BENCHMARK_MODE", "1")
    # Mock dependencies
    db = MagicMock()
    qdrant = MagicMock()
    
    router = MemoryRouter(db, qdrant)
    
    router._classify = AsyncMock(return_value={"strategy": "recall", "keywords": []})
    router._vector_search = AsyncMock(return_value=(["Vector Context"], ["doc1"], 0.5))
    router._assertion_search = MagicMock(return_value=([], [], 0.0))
    router._synthesize = AsyncMock(return_value="The answer is 42")

    with patch("src.retrieve.reranker.LocalReranker") as mock_reranker:
        mock_reranker.return_value.rerank = AsyncMock(return_value=["Vector Context"])
        result = await router.route_and_retrieve("proj-123", "What is X?")
    
    assert result["strategy"] == "recall"
    assert result["answer"] == "Vector Context"
    assert result["sources"] == ["doc1"]
    assert result["context"] == "Vector Context"
    assert "question_type" in result
    assert "recall_plan" in result

@pytest.mark.asyncio
async def test_router_research_strategy(monkeypatch):
    monkeypatch.setenv("RETRIEVE_BENCHMARK_MODE", "1")
    db = MagicMock()
    qdrant = MagicMock()
    router = MemoryRouter(db, qdrant)
    
    router._classify = AsyncMock(return_value={"strategy": "research", "keywords": ["Bob"]})
    router._graph_traversal = MagicMock(return_value=(["Graph Context"], ["node1"], 0.8))
    router._vector_search = AsyncMock(return_value=(["Vector Context"], ["doc1"], 0.9))
    router._assertion_search = MagicMock(return_value=([], [], 0.0))
    router._temporal_assertion_search = MagicMock(return_value=([], [], 0.0))
    router._persona_search = MagicMock(return_value=([], [], 0.0))
    router._event_graph_search = MagicMock(return_value=([], [], 0.0))
    router._session_summary_search = MagicMock(return_value=([], [], 0.0))
    router._contradiction_audit_search = MagicMock(return_value=([], [], 0.0))
    router._synthesize = AsyncMock(return_value="Complex Answer")

    with patch("src.retrieve.reranker.LocalReranker") as mock_reranker:
        mock_reranker.return_value.rerank = AsyncMock(
            return_value=["Graph Context", "Vector Context"]
        )
        result = await router.route_and_retrieve(
            "proj-123", "How did Bob's opinion about the project change over time?"
        )
    
    assert result["strategy"] == "research"
    assert "node1" in result["sources"]
    assert "doc1" in result["sources"]
    assert "Graph Context" in result["context"]
