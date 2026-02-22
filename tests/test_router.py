import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from src.retrieve.router import MemoryRouter

@pytest.mark.asyncio
async def test_router_classification():
    # Mock dependencies
    db = MagicMock()
    qdrant = MagicMock()
    
    router = MemoryRouter(db, qdrant)
    
    # Mock LLM response for classification
    # This requires mocking the `client.chat.completions.create` call inside the class
    # Since we can't easily patch the global client without Refactoring, 
    # we will mock the private _classify method for this unit test
    
    router._classify = AsyncMock(return_value={"strategy": "recall", "keywords": []})
    router._vector_search = AsyncMock(return_value=("Vector Context", ["doc1"]))
    router._synthesize = AsyncMock(return_value="The answer is 42")
    
    result = await router.route_and_retrieve("proj-123", "What is X?")
    
    assert result["strategy"] == "recall"
    assert result["answer"] == "The answer is 42"
    assert result["sources"] == ["doc1"]

@pytest.mark.asyncio
async def test_router_research_strategy():
    db = MagicMock()
    qdrant = MagicMock()
    router = MemoryRouter(db, qdrant)
    
    router._classify = AsyncMock(return_value={"strategy": "research", "keywords": ["Bob"]})
    router._graph_traversal = MagicMock(return_value=("Graph Context", ["node1"]))
    router._vector_search = AsyncMock(return_value=("Vector Context", ["doc1"]))
    router._synthesize = AsyncMock(return_value="Complex Answer")
    
    result = await router.route_and_retrieve("proj-123", "Who is Bob?")
    
    assert result["strategy"] == "research"
    # Sources should combine
    assert "node1" in result["sources"]
    assert "doc1" in result["sources"]
