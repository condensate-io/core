import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from src.retrieve.router import MemoryRouter

@pytest.mark.asyncio
async def test_router_classification():
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
    assert result["answer"] == "The answer is 42"
    assert result["sources"] == ["doc1"]
    assert result["context"] == "Vector Context"

@pytest.mark.asyncio
async def test_router_research_strategy():
    db = MagicMock()
    qdrant = MagicMock()
    router = MemoryRouter(db, qdrant)
    
    router._classify = AsyncMock(return_value={"strategy": "research", "keywords": ["Bob"]})
    router._graph_traversal = MagicMock(return_value=(["Graph Context"], ["node1"], 0.8))
    router._vector_search = AsyncMock(return_value=(["Vector Context"], ["doc1"], 0.9))
    router._assertion_search = MagicMock(return_value=([], [], 0.0))
    router._synthesize = AsyncMock(return_value="Complex Answer")

    with patch("src.retrieve.reranker.LocalReranker") as mock_reranker:
        mock_reranker.return_value.rerank = AsyncMock(
            return_value=["Graph Context", "Vector Context"]
        )
        result = await router.route_and_retrieve("proj-123", "Who is Bob?")
    
    assert result["strategy"] == "research"
    assert "node1" in result["sources"]
    assert "doc1" in result["sources"]
    assert "Graph Context" in result["context"]
