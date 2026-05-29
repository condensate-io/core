from unittest.mock import MagicMock

from src.retrieve.router import (
    episodic_score_adjustment,
    extract_query_keywords,
    extract_entity_names,
    filter_adversarial_context,
    format_episodic_context_line,
    heuristic_rerank_items,
    is_adversarial_risk_query,
    is_boilerplate_episodic,
    is_multihop_query,
    is_research_query,
    is_structured_context_line,
    is_temporal_query,
    merge_retrieval_items,
    normalize_chunk_text,
    qdrant_vector_search,
    supplementary_vector_queries,
    supplementary_vector_queries_recall,
)
def test_extract_query_keywords_filters_stopwords():
    keywords = extract_query_keywords("When did Caroline go to the LGBTQ support group?")
    assert "caroline" in keywords
    assert "lgbtq" in keywords
    assert "when" not in keywords


def test_is_research_query_temporal_and_multihop():
    assert is_research_query("When did Melanie paint a sunrise?")
    assert is_research_query("What fields would Caroline be likely to pursue in her educaton?")


def test_is_multihop_query():
    assert is_multihop_query("What fields would Caroline be likely to pursue in her educaton?")
    assert is_multihop_query(
        "Would Caroline still want to pursue counseling as a career if she hadn't received support growing up?"
    )
    assert not is_multihop_query("When did Caroline go to the LGBTQ support group?")


def test_normalize_chunk_text_strips_speaker_prefix():
    assert normalize_chunk_text("Caroline: Hello there.") == normalize_chunk_text("Hello there.")


def test_supplementary_vector_queries_multihop():
    query = (
        "Would Caroline still want to pursue counseling as a career "
        "if she hadn't received support growing up?"
    )
    keywords = extract_query_keywords(query)
    extras = supplementary_vector_queries(query, keywords)
    assert extras
    assert any("caroline" in e.lower() for e in extras)


def test_extract_entity_names():
    assert extract_entity_names("When did Caroline meet Melanie?") == ["Caroline", "Melanie"]


def test_supplementary_queries_include_psychology_for_fields_question():
    query = "What fields would Caroline be likely to pursue in her educaton?"
    extras = supplementary_vector_queries(query, extract_query_keywords(query))
    assert any("psychology" in e.lower() for e in extras)
    assert is_boilerplate_episodic("Melanie: Thanks, Caroline. They're a real support.")
    assert not is_boilerplate_episodic(
        "Caroline: I'm keen on counseling or working in mental health."
    )


def test_episodic_score_adjustment_downranks_boilerplate():
    low = episodic_score_adjustment("Melanie: Thanks!", 0.8)
    high = episodic_score_adjustment(
        "Caroline: psychology and counseling certification",
        0.8,
        metadata={"kind": "observation"},
    )
    assert low < high


def test_supplementary_vector_queries_recall():
    query = "What do Melanie's kids like?"
    extras = supplementary_vector_queries_recall(query, extract_query_keywords(query))
    assert extras
    assert "melanie" in extras[0].lower()


def test_heuristic_rerank_items_prefers_observations():
    items = [
        "Melanie: Thanks for your support.",
        "[observation D6:6] Melanie's kids love dinosaurs and nature.",
        "Caroline: Hey Mel!",
    ]
    ranked = heuristic_rerank_items("What do Melanie's kids like?", items, top_n=2)
    assert any("observation" in line.lower() for line in ranked)


def test_is_adversarial_risk_query():
    assert is_adversarial_risk_query("What are Melanie's plans for the summer with respect to adoption?")
    assert not is_adversarial_risk_query("When did Caroline go to the LGBTQ support group?")


def test_filter_adversarial_context_limits_raw_dialog(monkeypatch):
    monkeypatch.setenv("RETRIEVE_ADVERSARIAL_RAW_LIMIT", "1")
    items = [
        "[observation D2:8] Melanie is researching adoption agencies.",
        "Melanie: We might adopt this summer!",
        "Caroline: That's wonderful!",
    ]
    sources = ["a", "b", "c"]
    filtered_items, filtered_sources = filter_adversarial_context(items, sources)
    assert filtered_items[0].startswith("[observation")
    assert len(filtered_items) == 2


def test_is_structured_context_line():
    assert is_structured_context_line("[observation D1:3] fact")
    assert is_structured_context_line("Assertion: Caroline likes art (conf: 0.9)")
    assert not is_structured_context_line("Melanie: Hello there")


def test_is_temporal_query():
    assert is_temporal_query("When did Caroline go to the LGBTQ support group?")
    assert is_temporal_query("What did John do in 2022?")
    assert not is_temporal_query("What is Caroline's dog's name?")


def test_format_episodic_context_line_prefers_session_date():
    line = format_episodic_context_line(
        "Caroline: I went yesterday.",
        {"session_date": "1:56 pm on 8 May, 2023"},
        score=0.82,
    )
    assert "session @ 1:56 pm on 8 May, 2023" in line
    assert "Caroline" in line


def test_merge_retrieval_items_deduplicates():
    items, sources = merge_retrieval_items(
        (["a", "b"], ["1", "2"]),
        (["b", "c"], ["2", "3"]),
    )
    assert items == ["a", "b", "c"]
    assert sources == ["1", "2", "3"]

def test_qdrant_vector_search_uses_query_points():
    point = MagicMock()
    point.score = 0.9
    response = MagicMock(points=[point])
    client = MagicMock(query_points=MagicMock(return_value=response))

    hits = qdrant_vector_search(
        client,
        collection_name="episodic_chunks",
        query_vector=[0.1, 0.2],
        search_filter=None,
        limit=5,
    )

    assert hits == [point]
    client.query_points.assert_called_once()
    client.search.assert_not_called()
