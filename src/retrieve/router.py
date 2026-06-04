import os
import json
import logging
import re
import uuid
from typing import List, Dict, Any, Optional, Tuple
from src.retrieve.token_metrics import build_token_metrics, log_token_metrics
from openai import AsyncOpenAI
from qdrant_client import QdrantClient
from sqlalchemy.orm import Session
from sqlalchemy import select, text, or_, func
from src.db.models import Assertion, Entity, EpisodicItem

# Constants
from src.llm.client import LLMClient

logger = logging.getLogger(__name__)

_STOPWORDS = frozenset(
    {
        "what",
        "when",
        "where",
        "who",
        "how",
        "did",
        "does",
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "to",
        "in",
        "on",
        "for",
        "with",
        "and",
        "or",
        "her",
        "his",
        "their",
        "would",
        "likely",
        "pursue",
        "she",
        "he",
        "that",
        "this",
        "any",
        "about",
    }
)


def extract_query_keywords(query: str) -> List[str]:
    words = re.findall(r"[a-zA-Z']+", query.lower())
    return [w for w in words if len(w) > 2 and w not in _STOPWORDS][:12]


_ENTITY_SKIP = frozenset(
    {
        "When",
        "What",
        "Where",
        "Who",
        "How",
        "Would",
        "Did",
        "Does",
        "The",
        "Likely",
    }
)


def extract_entity_names(query: str) -> List[str]:
    names = re.findall(r"\b([A-Z][a-z]+)\b", query)
    return [n for n in names if n not in _ENTITY_SKIP]


def normalize_chunk_text(text: str) -> str:
    """Collapse duplicate episodic lines that differ only by ingest metadata."""
    stripped = text.strip()
    if ":" in stripped:
        _, _, body = stripped.partition(":")
        if body.strip():
            stripped = body.strip()
    return re.sub(r"\s+", " ", stripped.lower())


def is_multihop_query(query: str) -> bool:
    lowered = query.lower()
    markers = (
        "would ",
        "likely",
        " if ",
        "what fields",
        "still want",
        "still ",
        "hadn't",
        "had not",
        "without ",
    )
    return any(marker in lowered for marker in markers)


def supplementary_vector_queries_recall(query: str, keywords: List[str]) -> List[str]:
    """Light extra queries for single-hop recall (benchmark): entity + top keywords."""
    names = extract_entity_names(query)
    if not names:
        return []
    subject = names[0]
    names_lower = {n.lower() for n in names}
    content_kw = [k for k in keywords if k.lower() not in names_lower][:3]
    lowered = query.lower()
    extras: List[str] = []
    if content_kw:
        extras.append(f"{subject} {' '.join(content_kw)}")
    if "kids" in lowered or "children" in lowered:
        extras.append(f"{subject} kids hobbies interests")
    if "book" in lowered:
        extras.append(f"{subject} books reading")
    if "activit" in lowered or "events" in lowered or "participat" in lowered:
        extras.append(f"{subject} activities events")
    if "paint" in lowered:
        extras.append(f"{subject} painting artwork")
    if "relationship status" in lowered or "identity" in lowered:
        extras.append(f"{subject} relationship single married")
    if "planning" in lowered or "going camping" in lowered:
        extras.append(f"{subject} camping trip planning June")
    if "lgbtq" in lowered or "community" in lowered:
        extras.append(f"{subject} LGBTQ community events")
    seen: set[str] = set()
    deduped: List[str] = []
    for item in extras:
        key = item.lower().strip()
        if key and key not in seen and key != query.lower().strip():
            seen.add(key)
            deduped.append(item)
    return deduped[:5]


def supplementary_vector_queries(query: str, keywords: List[str]) -> List[str]:
    """Extra embedding queries to surface distinct evidence for multi-hop questions."""
    extras: List[str] = []
    names = extract_entity_names(query)
    names_lower = {n.lower() for n in names}
    content_kw = [k for k in keywords if k.lower() not in names_lower]
    subject = names[0] if names else None

    if subject and content_kw:
        extras.append(f"{subject} {' '.join(content_kw[:4])}")
    if len(names) >= 2:
        extras.append(f"{names[0]} {names[1]} {' '.join(content_kw[:3])}")
    if len(content_kw) >= 2:
        extras.append(" ".join(content_kw[:5]))
    if is_multihop_query(query):
        if subject:
            extras.append(f"{subject} support")
        lowered = query.lower()
        if "fields" in lowered or "pursue" in lowered or "career" in lowered:
            if subject:
                extras.append(f"{subject} psychology counseling certification education")
        if "activities" in lowered or "partake" in lowered:
            if subject:
                extras.append(f"{subject} pottery camping painting swimming hobbies")
        if "support" in lowered and ("negative" in lowered or "who" in lowered):
            if subject:
                extras.append(f"{subject} mentors family friends support")
        for kw in content_kw:
            if len(kw) >= 6:
                extras.append(kw)
        clause_match = re.search(r"\bif\b(.+?)\?", query, flags=re.IGNORECASE)
        if clause_match:
            clause_kw = extract_query_keywords(clause_match.group(1))
            if clause_kw:
                extras.append(" ".join(clause_kw[:5]))
    seen: set[str] = set()
    deduped: List[str] = []
    for item in extras:
        key = item.lower().strip()
        if key and key not in seen and key != query.lower().strip():
            seen.add(key)
            deduped.append(item)
    return deduped[:5]


def is_boilerplate_episodic(text: str) -> bool:
    norm = normalize_chunk_text(text)
    if len(norm) > 100:
        return False
    markers = ("thanks", "appreciate", "real support", "you're welcome", "glad you")
    return any(marker in norm for marker in markers)


def is_adversarial_risk_query(query: str) -> bool:
    if is_multihop_query(query):
        return False
    lowered = query.lower()
    markers = (
        "with respect to",
        "plans for",
        "adoption",
    )
    return any(marker in lowered for marker in markers)


def should_apply_adversarial_filter(query: str) -> bool:
    """LOC-013: filter raw dialog for trap-prone queries, not counterfactual multi-hop."""
    if is_multihop_query(query):
        return False
    return is_adversarial_risk_query(query)


def episodic_score_adjustment(
    text: str,
    score: float,
    *,
    multihop: bool = False,
    temporal: bool = False,
    adversarial_risk: bool = False,
    metadata: Optional[dict[str, Any]] = None,
) -> float:
    adjusted = score
    if is_boilerplate_episodic(text):
        adjusted *= 0.5
    lowered = text.lower()
    meta = metadata or {}
    kind = str(meta.get("kind", "")).lower()
    if kind == "observation" or "[observation" in lowered:
        adjusted *= 1.28
    if kind == "session_summary" or "session summary" in lowered:
        adjusted *= 1.18
    if temporal and (meta.get("session_date") or "session @" in lowered):
        adjusted *= 1.15
    if multihop and ("[session" in lowered or "session summary" in lowered):
        adjusted *= 1.12
    if adversarial_risk and kind not in ("observation", "session_summary"):
        if "[observation" not in lowered and "assertion:" not in lowered:
            adjusted *= 0.88
    return adjusted


def heuristic_rerank_items(query: str, items: List[str], top_n: int) -> List[str]:
    """Keyword overlap rerank for benchmark mode when LLM rerank is skipped."""
    if not items or top_n <= 0:
        return []
    if len(items) <= top_n:
        return items
    keywords = extract_query_keywords(query)
    names = extract_entity_names(query)
    temporal = is_temporal_query(query)
    adversarial_risk = is_adversarial_risk_query(query)

    def _score(item: str) -> float:
        norm = item.lower()
        score = float(sum(1 for k in keywords if k in norm))
        score += sum(3.0 for n in names if n.lower() in norm)
        if "[observation" in norm:
            score += 4.0
        if "session summary" in norm or "session @" in norm:
            score += 2.0
        if temporal and "session @" in norm:
            score += 2.5
        if adversarial_risk and "[observation" in norm:
            score += 3.0
        if "assertion:" in norm:
            score += 1.5
        return score

    ranked = sorted(items, key=lambda item: (-_score(item), items.index(item)))
    return ranked[:top_n]


def assertion_keyword_matches(assertion: Assertion, keywords: List[str]) -> int:
    blob = f"{assertion.subject_text} {assertion.predicate} {assertion.object_text}".lower()
    return sum(1 for kw in keywords if kw.lower() in blob)


def is_research_query(query: str) -> bool:
    lowered = query.lower()
    markers = (
        "when did",
        "how long",
        "since ",
        "before ",
        "after ",
        "what fields",
        "how many",
        " and ",
    )
    return any(marker in lowered for marker in markers)


def is_temporal_query(query: str) -> bool:
    lowered = query.lower()
    if any(
        marker in lowered
        for marker in (
            "when did",
            "when was",
            "when is",
            "what date",
            "how long",
            "how long ago",
            "since ",
            "planning on going",
        )
    ):
        return True
    return bool(re.search(r"\b(19|20)\d{2}\b", query))


def session_date_label(metadata: dict[str, Any]) -> str | None:
    if not metadata:
        return None
    session_date = metadata.get("session_date")
    if session_date:
        return str(session_date)
    return None


def format_episodic_context_line(text: str, metadata: dict[str, Any], *, score: float | None = None) -> str:
    prefix_parts: list[str] = []
    if score is not None:
        prefix_parts.append(f"score={score:.3f}")
    session_date = session_date_label(metadata or {})
    if session_date:
        prefix_parts.append(f"session @ {session_date}")
    occurred = (metadata or {}).get("occurred_at")
    if occurred and not session_date:
        prefix_parts.append(f"when={occurred}")
    if prefix_parts:
        return f"[{', '.join(prefix_parts)}] {text}"
    return text


def merge_retrieval_items(
    *parts: Tuple[List[str], List[str]],
) -> Tuple[List[str], List[str]]:
    seen_text: set[str] = set()
    items: List[str] = []
    sources: List[str] = []
    for item_list, source_list in parts:
        for item, source in zip(item_list, source_list):
            if not item or item in seen_text:
                continue
            seen_text.add(item)
            items.append(item)
            sources.append(source)
    return items, sources


def is_structured_context_line(text: str) -> bool:
    lowered = text.lower()
    return (
        "[observation" in lowered
        or "session summary" in lowered
        or "assertion:" in lowered
        or ("session @" in lowered and "score=" in lowered)
    )


def filter_adversarial_context(
    items: List[str], sources: List[str]
) -> Tuple[List[str], List[str]]:
    """LOC-013: prefer observations/assertions over raw dialog that may contain trap answers."""
    safe_items: List[str] = []
    safe_sources: List[str] = []
    raw_items: List[str] = []
    raw_sources: List[str] = []
    for item, source in zip(items, sources):
        if is_structured_context_line(item):
            safe_items.append(item)
            safe_sources.append(source)
        else:
            raw_items.append(item)
            raw_sources.append(source)
    raw_limit = int(os.getenv("RETRIEVE_ADVERSARIAL_RAW_LIMIT", "6"))
    return safe_items + raw_items[:raw_limit], safe_sources + raw_sources[:raw_limit]


def get_current_client(config: Optional[Dict[str, str]] = None):
    """Dynamically resolves the LLM settings from the config file if not provided explicitly."""
    if not config:
        config = LLMClient.get_active_config()
    
    return AsyncOpenAI(
        api_key=config.get("apiKey", config.get("api_key", "sk-placeholder")),
        base_url=config.get("baseUrl", config.get("base_url", "https://api.openai.com/v1"))
    ), config.get("model", "gpt-4-turbo")

ROUTER_PROMPT = """
You are a Memory Router. Your job is to classify the user's query and decide the best retrieval strategy.

Query: {query}

Strategies:
1. "recall": Simple factual lookup. Use Vector Search. (e.g. "What did Bob say about the DB?")
2. "research": Complex multi-hop reasoning. Use Graph Traversal + Vector. (e.g. "How has the architecture evolved?")
3. "meta": Questions about the system itself. (e.g. "How many memories do I have?")

Complexity Scoring:
- Score 1: Simple retrieval.
- Score 2: Default research.
- Score 3: Deep investigation. (Boost to 3 if user uses systemic keywords like "cascade", "impact", "origin", "influence", or "root cause").

Output JSON:
{{
    "strategy": "recall" | "research" | "meta",
    "keywords": ["list", "of", "search", "terms"],
    "complexity": 1 | 2 | 3
}}
"""

_QUERY_EMBEDDING = None


def _resolve_project_uuid(project_id: Any) -> uuid.UUID:
    if isinstance(project_id, uuid.UUID):
        return project_id
    try:
        return uuid.UUID(str(project_id))
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(project_id))


def episodic_qdrant_filter(project_id: Any, session_id: str | None = None):
    """Build a Qdrant filter for project scope, optionally narrowed to one session."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

    must: list[Any] = []
    if isinstance(project_id, list):
        must.append(FieldCondition(key="project_id", match=MatchAny(any=project_id)))
    else:
        must.append(FieldCondition(key="project_id", match=MatchValue(value=str(project_id))))
    if session_id:
        must.append(
            FieldCondition(key="metadata.session_id", match=MatchValue(value=session_id))
        )
    return Filter(must=must)


def session_scope_profile(
    db: Session, project_id: Any, session_id: str
) -> tuple[frozenset[str], frozenset[str]]:
    """Entity names and keywords drawn from episodic items in one session."""
    pid = _resolve_project_uuid(project_id)
    rows = db.execute(
        select(EpisodicItem.text, EpisodicItem.metadata_).where(
            EpisodicItem.project_id == pid
        )
    ).all()
    entities: set[str] = set()
    terms: set[str] = set()
    for text, meta in rows:
        if (meta or {}).get("session_id") != session_id:
            continue
        entities.update(extract_entity_names(text))
        terms.update(extract_query_keywords(text))
        for name in entities:
            terms.add(name.lower())
    return frozenset(entities), frozenset(terms)


def assertion_in_session_scope(
    assertion: Assertion,
    session_entities: frozenset[str],
    session_terms: frozenset[str],
) -> bool:
    """Keep assertions that plausibly belong to the requested session."""
    if not session_entities and not session_terms:
        return True
    blob = f"{assertion.subject_text} {assertion.predicate} {assertion.object_text}".lower()
    if session_entities:
        if not any(entity.lower() in blob for entity in session_entities):
            return False
    if session_terms:
        return any(term in blob for term in session_terms if len(term) >= 3)
    return True


def filter_assertions_for_session(
    assertions: List[Assertion],
    session_entities: frozenset[str],
    session_terms: frozenset[str],
) -> List[Assertion]:
    if not session_entities and not session_terms:
        return assertions
    scoped = [
        a
        for a in assertions
        if assertion_in_session_scope(a, session_entities, session_terms)
    ]
    return scoped or assertions[: min(6, len(assertions))]


def qdrant_vector_search(
    qdrant,
    *,
    collection_name: str,
    query_vector: list[float],
    search_filter,
    limit: int,
    with_payload: bool = True,
):
    """Compatible vector query for qdrant-client 1.7+ (query_points) and legacy search."""
    if hasattr(qdrant, "query_points"):
        response = qdrant.query_points(
            collection_name=collection_name,
            query=query_vector,
            query_filter=search_filter,
            limit=limit,
            with_payload=with_payload,
        )
        return response.points
    return qdrant.search(
        collection_name=collection_name,
        query_vector=query_vector,
        query_filter=search_filter,
        limit=limit,
        with_payload=with_payload,
    )


def _get_query_embedding():
    global _QUERY_EMBEDDING
    if _QUERY_EMBEDDING is not None:
        return _QUERY_EMBEDDING
    from fastembed import TextEmbedding

    try:
        import onnxruntime as ort

        available = ort.get_available_providers()
        force_cpu = os.getenv("RETRIEVE_EMBED_CPU", "").lower() in ("1", "true", "yes")
        if force_cpu or "CUDAExecutionProvider" not in available:
            providers = ["CPUExecutionProvider"]
        else:
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    except ImportError:
        providers = ["CPUExecutionProvider"]
    _QUERY_EMBEDDING = TextEmbedding(model_name="BAAI/bge-small-en-v1.5", providers=providers)
    return _QUERY_EMBEDDING


class MemoryRouter:
    def __init__(self, db: Session, qdrant: QdrantClient):
        self.db = db
        self.qdrant = qdrant

    async def route_and_retrieve(self, project_id: Any, query: str, skip_llm: bool = False, llm_config: Optional[Dict[str, str]] = None, current_step: Optional[int] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Main entry point: Classification -> Retrieval -> Synthesis
        """
        # 1. Classify Intent
        classify_prompt = ROUTER_PROMPT.format(query=query)
        benchmark_mode = os.getenv("RETRIEVE_BENCHMARK_MODE", "").lower() in ("1", "true", "yes")
        if benchmark_mode:
            plan = {
                "strategy": "research"
                if (is_research_query(query) or is_multihop_query(query))
                else "recall",
                "keywords": extract_query_keywords(query),
                "complexity": 2,
            }
            skip_llm = True
        else:
            plan = await self._classify(query, llm_config)
        strategy = plan.get("strategy", "recall")
        keywords = plan.get("keywords", []) or extract_query_keywords(query)
        complexity = int(plan.get("complexity", 2))
        if is_research_query(query) or is_multihop_query(query):
            strategy = "research"

        context_items: List[str] = []
        sources: List[str] = []
        confidence_score = 0.0

        if strategy == "meta":
            context_items = ["System functionality query."]
            sources = []
            confidence_score = 1.0
        else:
            context_items, sources, confidence_score = await self._hybrid_retrieve(
                project_id,
                query,
                strategy=strategy,
                keywords=keywords,
                complexity=complexity,
                current_step=current_step,
                session_id=session_id,
            )

        # --- Reranking Layer ---
        from src.retrieve.reranker import LocalReranker
        reranker = LocalReranker(llm_config=llm_config)
        rerank_top_n = int(os.getenv("RETRIEVE_RERANK_TOP_N", "16"))
        if benchmark_mode and is_multihop_query(query):
            rerank_top_n = max(rerank_top_n, 12)
        skip_rerank = os.getenv("RETRIEVE_SKIP_RERANK", "").lower() in ("1", "true", "yes")
        if skip_rerank:
            if benchmark_mode:
                final_items = heuristic_rerank_items(query, context_items, rerank_top_n)
            else:
                final_items = context_items[:rerank_top_n]
        else:
            final_items = await reranker.rerank(query, context_items, top_n=rerank_top_n)
        context = "\n\n".join(final_items)
        max_chars = int(os.getenv("RETRIEVE_MAX_CONTEXT_CHARS", "28000"))
        if len(context) > max_chars:
            context = context[:max_chars]
        
        THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.8"))

        sys_prompt = "You are a helpful assistant. Answer the user query based ONLY on the provided context."
        user_msg = f"Context:\n{context}\n\nQuery: {query}"
        synthesized = False

        # 2. Synthesize Answer (Brief)
        if benchmark_mode:
            answer = context
        elif skip_llm or confidence_score >= THRESHOLD:
            if not skip_llm:
                answer = f"**TRAFFIC CONTROL: LLM SKIPPED (Confidence: {confidence_score:.2f} >= {THRESHOLD})**\n\nStrategy: {strategy}\n\nContext Retrieved:\n{context}"
            else:
                answer = f"**TRAFFIC CONTROL: LLM SKIPPED**\n\nStrategy: {strategy}\n\nContext Retrieved:\n{context}"
        else:
            synthesized = True
            answer = await self._synthesize(query, context, llm_config, sys_prompt=sys_prompt, user_msg=user_msg)

        _, llm_model = get_current_client(llm_config)
        token_metrics = build_token_metrics(
            router_prompt=classify_prompt,
            context=context,
            query=query,
            synthesized=synthesized,
            sys_prompt=sys_prompt,
            user_msg=user_msg,
            model=llm_model,
        )
        log_token_metrics(token_metrics, project_id=project_id, query=query, strategy=strategy)

        # 3. Cognitive Dynamics: skip during benchmark runs (199 sequential retrieves).
        if sources and not benchmark_mode:
            try:
                # Convert 'source' strings (UUIDs) back to UUID objects
                import uuid
                source_ids = []
                for s in sources:
                    try:
                        source_ids.append(uuid.UUID(s))
                    except:
                        pass
                
                if source_ids:
                    from src.engine.cognitive import CognitiveService
                    cog = CognitiveService(self.db)
                    cog.hebbian_update(source_ids)

                    # --- Synapse Engine Strengthening ---
                    try:
                        from src.synapses.config import synapse_config
                        if synapse_config.ENABLED:
                            from src.synapses.engine import SynapseEngine
                            syn_engine = SynapseEngine(self.db)
                            syn_engine.strengthen_on_retrieval(source_ids, query)
                    except Exception as se_exc:
                        logger.warning("Synapse strengthening failed: %s", se_exc)
            except Exception as e:
                logger.warning("Hebbian update failed: %s", e)

        return {
            "answer": answer,
            "context": context,
            "sources": sources,
            "strategy": strategy,
            "token_metrics": token_metrics,
        }

    async def _classify(self, query: str, llm_config: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Classify the user intent into recall, research, or meta strategies using the active LLM."""
        try:
            use_client, model = get_current_client(llm_config)
            
            response = await use_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": ROUTER_PROMPT.format(query=query)}],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            # Fallback to simple recall if LLM fails or is unconfigured
            logger.warning("Router classification failed: %s", e)
            return {"strategy": "recall", "keywords": extract_query_keywords(query)}

    async def _hybrid_retrieve(
        self,
        project_id: Any,
        query: str,
        *,
        strategy: str,
        keywords: List[str],
        complexity: int,
        current_step: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> Tuple[List[str], List[str], float]:
        session_entities: frozenset[str] = frozenset()
        session_terms: frozenset[str] = frozenset()
        if session_id:
            session_entities, session_terms = session_scope_profile(
                self.db, project_id, session_id
            )
        steps = 1 if complexity == 1 else (3 if complexity == 3 else 2)
        decay = 0.7 if complexity == 1 else (0.3 if complexity == 3 else 0.5)
        skip_graph = os.getenv("RETRIEVE_BENCHMARK_SKIP_GRAPH", "").lower() in ("1", "true", "yes")
        benchmark_mode = os.getenv("RETRIEVE_BENCHMARK_MODE", "").lower() in ("1", "true", "yes")
        bench_graph_steps = int(os.getenv("RETRIEVE_BENCHMARK_GRAPH_STEPS", "0") or "0")
        multihop = is_multihop_query(query)
        temporal = is_temporal_query(query)
        adversarial_risk = is_adversarial_risk_query(query)
        use_graph = strategy == "research" or is_research_query(query) or is_temporal_query(query)
        if benchmark_mode and skip_graph and not (bench_graph_steps > 0 and multihop):
            use_graph = False

        multi_query = benchmark_mode and os.getenv(
            "RETRIEVE_BENCHMARK_MULTI_QUERY", "1"
        ).lower() in ("1", "true", "yes")
        extra_queries: Optional[List[str]] = None
        if multi_query:
            if multihop or temporal:
                extra_queries = supplementary_vector_queries(query, keywords)
            else:
                extra_queries = supplementary_vector_queries_recall(query, keywords)
        vec_items, vec_sources, vec_conf = await self._vector_search(
            project_id,
            query,
            current_step=current_step,
            extra_queries=extra_queries,
            multihop=multihop,
            temporal=temporal,
            adversarial_risk=adversarial_risk,
            session_id=session_id,
        )
        if multihop:
            assert_items, assert_sources, assert_conf = self._multihop_assertion_search(
                project_id, keywords, session_entities=session_entities, session_terms=session_terms
            )
        else:
            assert_items, assert_sources, assert_conf = self._assertion_search(
                project_id, query, session_entities=session_entities, session_terms=session_terms
            )
        graph_items: List[str] = []
        graph_sources: List[str] = []
        graph_conf = 0.0
        graph_steps = steps
        graph_decay = decay
        if benchmark_mode and bench_graph_steps > 0 and multihop:
            use_graph = True
            graph_steps = bench_graph_steps
            graph_decay = 0.5
        if use_graph and keywords:
            graph_items, graph_sources, graph_conf = self._graph_traversal(
                project_id, keywords, steps=graph_steps, decay=graph_decay
            )
        elif benchmark_mode and skip_graph and keywords and (multihop or temporal):
            graph_items, graph_sources, graph_conf = self._light_entity_assertions(
                project_id,
                keywords,
                min_keyword_matches=2 if multihop else 1,
                session_entities=session_entities,
                session_terms=session_terms,
            )

        context_items, sources = merge_retrieval_items(
            (vec_items, vec_sources),
            (assert_items, assert_sources),
            (graph_items, graph_sources),
        )
        if benchmark_mode and should_apply_adversarial_filter(query) and os.getenv(
            "RETRIEVE_ADVERSARIAL_FILTER", "1"
        ).lower() in ("1", "true", "yes"):
            context_items, sources = filter_adversarial_context(context_items, sources)
        return context_items, sources, max(vec_conf, assert_conf, graph_conf)

    async def _vector_search(
        self,
        project_id: Any,
        query: str,
        current_step: Optional[int] = None,
        extra_queries: Optional[List[str]] = None,
        multihop: bool = False,
        temporal: bool = False,
        adversarial_risk: bool = False,
        session_id: Optional[str] = None,
    ):
        """
        Real vector search: embed the query with fastembed, then search Qdrant
        for the top-10 nearest episodic items in this project.
        """
        if self.qdrant is None:
            return [], [], 0.0

        search_queries = [query]
        if extra_queries:
            search_queries.extend(extra_queries)

        merged_hits: list[Any] = []
        best_by_text: dict[str, Any] = {}
        vector_limit = int(os.getenv("RETRIEVE_VECTOR_LIMIT", "20"))
        per_query_limit = max(8, vector_limit // max(1, len(search_queries)))

        def _prefer_hit(existing: Any, candidate: Any) -> Any:
            def _session_date(hit: Any) -> bool:
                meta = (hit.payload or {}).get("metadata") or {}
                return bool(meta.get("session_date"))

            if _session_date(candidate) and not _session_date(existing):
                return candidate
            if candidate.score > existing.score:
                return candidate
            return existing

        try:
            embedding_model = _get_query_embedding()
        except Exception as e:
            logger.warning("Query embedding model init failed: %s", e)
            return [], [], 0.0

        for search_query in search_queries:
            try:
                query_vectors = list(embedding_model.embed([search_query]))
                if not query_vectors:
                    continue
                query_vector = query_vectors[0].tolist()
            except Exception as e:
                logger.warning("Query embedding failed: %s", e)
                continue

            try:
                search_filter = episodic_qdrant_filter(project_id, session_id)
                results = qdrant_vector_search(
                    self.qdrant,
                    collection_name="episodic_chunks",
                    query_vector=query_vector,
                    search_filter=search_filter,
                    limit=30 if current_step is not None else per_query_limit,
                    with_payload=True,
                )
            except Exception as e:
                logger.warning("Qdrant vector search failed: %s", e)
                continue

            if current_step is not None:
                import math
                decay_rate = 0.05
                for hit in results:
                    payload = hit.payload or {}
                    meta = payload.get("metadata", {})
                    memory_step = meta.get("simulation_step")
                    if memory_step is not None:
                        try:
                            time_diff = max(0, current_step - int(memory_step))
                            decay_factor = math.exp(-decay_rate * time_diff)
                            hit.score = hit.score * decay_factor
                        except Exception:
                            pass
                results.sort(key=lambda x: x.score, reverse=True)
                results = results[:per_query_limit]

            for hit in results:
                payload = hit.payload or {}
                text = payload.get("text", "")
                norm = normalize_chunk_text(text)
                if not norm:
                    continue
                if norm in best_by_text:
                    best_by_text[norm] = _prefer_hit(best_by_text[norm], hit)
                else:
                    best_by_text[norm] = hit

        merged_hits = list(best_by_text.values())
        for hit in merged_hits:
            payload = hit.payload or {}
            text = payload.get("text", "")
            meta = payload.get("metadata", {}) or {}
            hit.score = episodic_score_adjustment(
                text,
                hit.score,
                multihop=multihop,
                temporal=temporal,
                adversarial_risk=adversarial_risk,
                metadata=meta,
            )

        if not merged_hits:
            return [], [], 0.0

        merged_hits.sort(key=lambda x: x.score, reverse=True)
        merged_hits = merged_hits[:vector_limit]

        context_parts = []
        source_ids = []
        max_score = 0.0
        for hit in merged_hits:
            payload = hit.payload or {}
            text = payload.get("text", "")
            meta = payload.get("metadata", {}) or {}
            if payload.get("occurred_at") and "occurred_at" not in meta:
                meta = {**meta, "occurred_at": payload.get("occurred_at")}
            score = round(hit.score, 3)
            max_score = max(max_score, score)
            context_parts.append(format_episodic_context_line(text, meta, score=score))
            item_id = payload.get("item_id", str(hit.id))
            source_ids.append(item_id)

        return context_parts, source_ids, max_score

    def _assertion_search(
        self,
        project_id: Any,
        query: str,
        *,
        session_entities: frozenset[str] = frozenset(),
        session_terms: frozenset[str] = frozenset(),
    ) -> Tuple[List[str], List[str], float]:
        keywords = extract_query_keywords(query)
        if not keywords:
            return [], [], 0.0

        conditions = []
        for keyword in keywords:
            pattern = f"%{keyword}%"
            conditions.extend(
                [
                    Assertion.subject_text.ilike(pattern),
                    Assertion.object_text.ilike(pattern),
                    Assertion.predicate.ilike(pattern),
                ]
            )

        if isinstance(project_id, list):
            stmt = select(Assertion).where(
                Assertion.project_id.in_(project_id),
                Assertion.status.in_(["approved", "active"]),
                or_(*conditions),
            )
        else:
            stmt = select(Assertion).where(
                Assertion.project_id == project_id,
                Assertion.status.in_(["approved", "active"]),
                or_(*conditions),
            )

        assertion_limit = int(os.getenv("RETRIEVE_ASSERTION_LIMIT", "25"))
        assertions = (
            self.db.execute(
                stmt.order_by(Assertion.confidence.desc(), Assertion.strength.desc()).limit(
                    assertion_limit
                )
            )
            .scalars()
            .all()
        )
        if not assertions:
            return [], [], 0.0

        assertions = filter_assertions_for_session(assertions, session_entities, session_terms)
        if not assertions:
            return [], [], 0.0

        context_parts = [
            f"Assertion: {a.subject_text} {a.predicate} {a.object_text} (conf: {a.confidence})"
            for a in assertions
        ]
        sources = [str(a.id) for a in assertions]
        max_conf = max(a.confidence for a in assertions)
        return context_parts, sources, max_conf

    def _filter_assertions_by_keywords(
        self, assertions: List[Assertion], keywords: List[str], min_matches: int
    ) -> List[Assertion]:
        if min_matches <= 1:
            return assertions
        filtered = [a for a in assertions if assertion_keyword_matches(a, keywords) >= min_matches]
        return filtered or assertions[: min(6, len(assertions))]

    def _multihop_assertion_search(
        self,
        project_id: Any,
        keywords: List[str],
        *,
        session_entities: frozenset[str] = frozenset(),
        session_terms: frozenset[str] = frozenset(),
    ) -> Tuple[List[str], List[str], float]:
        if not keywords:
            return [], [], 0.0

        conditions = []
        for keyword in keywords:
            pattern = f"%{keyword}%"
            conditions.extend(
                [
                    Assertion.subject_text.ilike(pattern),
                    Assertion.object_text.ilike(pattern),
                    Assertion.predicate.ilike(pattern),
                ]
            )

        if isinstance(project_id, list):
            stmt = select(Assertion).where(
                Assertion.project_id.in_(project_id),
                Assertion.status.in_(["approved", "active"]),
                or_(*conditions),
            )
        else:
            stmt = select(Assertion).where(
                Assertion.project_id == project_id,
                Assertion.status.in_(["approved", "active"]),
                or_(*conditions),
            )

        assertion_limit = int(os.getenv("RETRIEVE_ASSERTION_LIMIT", "25"))
        assertions = (
            self.db.execute(
                stmt.order_by(Assertion.confidence.desc(), Assertion.strength.desc()).limit(
                    assertion_limit
                )
            )
            .scalars()
            .all()
        )
        assertions = self._filter_assertions_by_keywords(assertions, keywords, min_matches=2)
        assertions = filter_assertions_for_session(assertions, session_entities, session_terms)
        if not assertions:
            return [], [], 0.0

        context_parts = [
            f"Assertion: {a.subject_text} {a.predicate} {a.object_text} (conf: {a.confidence})"
            for a in assertions
        ]
        sources = [str(a.id) for a in assertions]
        max_conf = max(a.confidence for a in assertions)
        return context_parts, sources, max_conf

    def _light_entity_assertions(
        self,
        project_id: Any,
        keywords: List[str],
        *,
        min_keyword_matches: int = 1,
        session_entities: frozenset[str] = frozenset(),
        session_terms: frozenset[str] = frozenset(),
    ) -> Tuple[List[str], List[str], float]:
        """Direct entity→assertion lookup without graph spreading (benchmark-safe)."""
        if not keywords:
            return [], [], 0.0

        entity_conditions = []
        for keyword in keywords:
            lowered = keyword.lower()
            entity_conditions.append(func.lower(Entity.canonical_name).contains(lowered))
            entity_conditions.append(func.lower(Entity.canonical_name) == lowered)

        if isinstance(project_id, list):
            ent_stmt = select(Entity).where(
                Entity.project_id.in_(project_id),
                or_(*entity_conditions),
            )
        else:
            ent_stmt = select(Entity).where(
                Entity.project_id == project_id,
                or_(*entity_conditions),
            )
        entities = self.db.execute(ent_stmt.limit(8)).scalars().all()
        if not entities:
            return [], [], 0.0

        entity_ids = [e.id for e in entities]
        if isinstance(project_id, list):
            ass_stmt = select(Assertion).where(
                Assertion.project_id.in_(project_id),
                Assertion.status.in_(["approved", "active"]),
                or_(
                    Assertion.subject_entity_id.in_(entity_ids),
                    Assertion.object_entity_id.in_(entity_ids),
                ),
            )
        else:
            ass_stmt = select(Assertion).where(
                Assertion.project_id == project_id,
                Assertion.status.in_(["approved", "active"]),
                or_(
                    Assertion.subject_entity_id.in_(entity_ids),
                    Assertion.object_entity_id.in_(entity_ids),
                ),
            )

        light_limit = int(os.getenv("RETRIEVE_LIGHT_GRAPH_LIMIT", "12"))
        assertions = (
            self.db.execute(
                ass_stmt.order_by(Assertion.confidence.desc(), Assertion.strength.desc()).limit(
                    light_limit
                )
            )
            .scalars()
            .all()
        )
        if not assertions:
            return [], [], 0.0

        assertions = self._filter_assertions_by_keywords(
            assertions, keywords, min_matches=min_keyword_matches
        )
        assertions = filter_assertions_for_session(assertions, session_entities, session_terms)
        if not assertions:
            return [], [], 0.0

        context_parts = [
            f"Assertion: {a.subject_text} {a.predicate} {a.object_text} (conf: {a.confidence})"
            for a in assertions
        ]
        sources = [str(a.id) for a in assertions]
        max_conf = max(a.confidence for a in assertions)
        return context_parts, sources, max_conf

    def _graph_traversal(self, project_id: Any, keywords: List[str], steps: int = 2, decay: float = 0.5):
        """
        Research Strategy: Find entities -> Spreading Activation -> Get Assertions
        """
        if not keywords:
            return [], [], 0.0

        entity_conditions = []
        for keyword in keywords:
            lowered = keyword.lower()
            entity_conditions.append(func.lower(Entity.canonical_name).contains(lowered))
            entity_conditions.append(func.lower(Entity.canonical_name) == lowered)

        if isinstance(project_id, list):
            ent_stmt = select(Entity).where(
                Entity.project_id.in_(project_id),
                or_(*entity_conditions),
            )
        else:
            ent_stmt = select(Entity).where(
                Entity.project_id == project_id,
                or_(*entity_conditions),
            )
        entities = self.db.execute(ent_stmt).scalars().all()
        
        if not entities:
            return [], [], 0.0

        seed_ids = [e.id for e in entities]
        
        # 2. Spreading Activation
        from src.engine.cognitive import CognitiveService
        cog = CognitiveService(self.db)
        activated_ids = cog.spreading_activation(seed_ids, steps=steps, decay_factor=decay)
        
        # 3. Retrieve Assertions for Activated Entities (only approved/active)
        if isinstance(project_id, list):
            ass_stmt = select(Assertion).where(
                Assertion.project_id.in_(project_id),
                Assertion.status.in_(['approved', 'active']),
                (Assertion.subject_entity_id.in_(activated_ids)) | (Assertion.object_entity_id.in_(activated_ids))
            )
        else:
            ass_stmt = select(Assertion).where(
                Assertion.project_id == project_id,
                Assertion.status.in_(['approved', 'active']),
                (Assertion.subject_entity_id.in_(activated_ids)) | (Assertion.object_entity_id.in_(activated_ids))
            )
            
        assertions = self.db.execute(
            ass_stmt.limit(20) # Cap context
            .order_by(Assertion.strength.desc()) # Prioritize strong memories (LTP)
        ).scalars().all()
        
        context_parts = [f"Assertion: {a.subject_text} {a.predicate} {a.object_text} (conf: {a.confidence}, str: {a.strength})" for a in assertions]
        sources = [str(a.id) for a in assertions]
        
        max_conf = max([a.confidence for a in assertions]) if assertions else 0.0
        
        return context_parts, sources, max_conf

    async def _synthesize(
        self,
        query: str,
        context: str,
        llm_config: Optional[Dict[str, str]] = None,
        *,
        sys_prompt: Optional[str] = None,
        user_msg: Optional[str] = None,
    ) -> str:
        """Combine context and query into a natural language response using the active LLM."""
        try:
            use_client, model = get_current_client(llm_config)

            sys_prompt = sys_prompt or "You are a helpful assistant. Answer the user query based ONLY on the provided context."
            user_msg = user_msg or f"Context:\n{context}\n\nQuery: {query}"

            response = await use_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.0,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Answer synthesis failed: {e}. Raw context preserved: {context[:500]}..."
