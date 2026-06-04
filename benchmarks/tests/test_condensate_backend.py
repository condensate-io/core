from unittest.mock import MagicMock, patch

from benchmarks.backends.condensate import CondensateBackend


def test_condensate_search_prefers_context_over_source_ids():
    backend = CondensateBackend(base_url="http://test")
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "answer": "LLM summary",
        "context": "[score=0.91] user: Caroline attended an LGBTQ support group on 7 May 2023.",
        "sources": ["e3592915-d9b8-4573-b65f-db0ce0cfc2b3"],
        "strategy": "recall",
    }
    response.raise_for_status = MagicMock()

    with patch.object(backend._client, "post", return_value=response) as post:
        text = backend.search("conv-26", "When did Caroline go to the LGBTQ support group?")

    assert "LGBTQ support group" in text
    assert "e3592915" not in text
    payload = post.call_args.kwargs.get("json") or post.call_args.args[1]
    assert payload["session_id"] == "conv-26"
