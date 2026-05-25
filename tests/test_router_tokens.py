import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.retrieve.router import ROUTER_PROMPT, MemoryRouter
from src.retrieve.token_metrics import build_token_metrics, count_context_items, count_tokens


def test_count_tokens_empty():
    assert count_tokens("") == 0


def test_count_tokens_non_empty():
    assert count_tokens("hello world") >= 1


def test_count_context_items():
    items = ["first chunk", "second chunk"]
    assert count_context_items(items) == count_tokens("first chunk\n\nsecond chunk")
    assert count_context_items([]) == 0


def test_build_token_metrics_synthesized():
    metrics = build_token_metrics(
        router_prompt=ROUTER_PROMPT.format(query="What is X?"),
        context="Vector Context",
        query="What is X?",
        synthesized=True,
        sys_prompt="system",
        user_msg="user",
    )
    assert metrics["router_classification"] > 0
    assert metrics["retrieved_context"] > 0
    assert metrics["total_answer_call"] > 0


@pytest.mark.asyncio
async def test_route_and_retrieve_includes_token_metrics():
    db = MagicMock()
    qdrant = MagicMock()
    router = MemoryRouter(db, qdrant)

    router._classify = AsyncMock(return_value={"strategy": "recall", "keywords": []})
    router._vector_search = AsyncMock(return_value=(["Vector Context"], ["doc1"], 0.5))
    router._synthesize = AsyncMock(return_value="The answer is 42")

    with patch("src.retrieve.reranker.LocalReranker") as mock_reranker_cls:
        mock_reranker = MagicMock()
        mock_reranker.rerank = AsyncMock(return_value=["Vector Context"])
        mock_reranker_cls.return_value = mock_reranker

        result = await router.route_and_retrieve("proj-123", "What is X?")

    assert "token_metrics" in result
    metrics = result["token_metrics"]
    assert metrics["router_classification"] == count_tokens(ROUTER_PROMPT.format(query="What is X?"))
    assert metrics["retrieved_context"] == count_tokens("Vector Context")
    assert metrics["total_answer_call"] > 0
    assert set(metrics.keys()) == {
        "router_classification",
        "retrieved_context",
        "answer_prompt",
        "total_answer_call",
    }
