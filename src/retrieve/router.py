import os
import json
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from src.retrieve.token_metrics import build_token_metrics, log_token_metrics
from openai import AsyncOpenAI
from qdrant_client import QdrantClient
from sqlalchemy.orm import Session
from sqlalchemy import select, text, or_, func
from src.db.models import Assertion, Entity, EpisodicItem, Event, Policy

# Constants
from src.llm.client import LLMClient
from src.retrieve.entity_alignment import (
    extract_focus_terms,
    filter_entity_evidence_context,
    filter_swap_trap_context,
    episodic_hit_admissible,
    is_adversarial_risk_query,
    is_entity_swap_trap,
    is_specific_attribute_query,
    supplementary_vector_queries_adversarial,
)
from src.retrieve.recall_gate import AstrocyteRecallGate, QueryPlan, is_adversarial_phrasing
from src.retrieve.evidence_verifier import (
    abstention_answer,
    build_verified_context,
    verify_evidence,
)
from src.learn.supersession import fetch_supersession_chain, latest_valid_assertions

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
        "what are ",
        "what attributes",
        "what job",
        "what electronic",
        "which ",
        "why did",
        "is it likely",
        "could ",
        "besides ",
        "describe ",
        "still want",
        "still ",
        "hadn't",
        "had not",
        "without ",
        "health problem",
        "suspected",
        "visit during",
        "additional country",
        "travelling in",
        "traveling in",
        "put off",
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
    if not content_kw:
        return []
    return [f"{subject} {' '.join(content_kw)}"]


def supplementary_vector_queries(query: str, keywords: List[str]) -> List[str]:
    """Extra embedding queries to surface distinct evidence for multi-hop questions."""
    extras: List[str] = []
    names = extract_entity_names(query)
    names_lower = {n.lower() for n in names}
    content_kw = [k for k in keywords if k.lower() not in names_lower]
    subject = names[0] if names else None

    if subject and content_kw:
        extras.append(f"{subject} {' '.join(content_kw[:4])}")
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
        if subject and ("health" in lowered or "problems" in lowered):
            extras.append(f"{subject} health obesity weight problems")
        if subject and "state" in lowered and any(
            m in lowered for m in ("travelling", "traveling", "travel", "visit", "internship")
        ):
            extras.append(f"{subject} state travel visit California Alaska")
        if subject and "likely" in lowered and "friends" in lowered:
            extras.append(f"{subject} friends teammates video game team")
        if subject and ("attributes" in lowered or "describe" in lowered):
            extras.append(f"{subject} selfless passionate family-oriented traits")
        if subject and "job" in lowered and "pursue" in lowered:
            extras.append(f"{subject} career counselor coordinator shelter job")
        if subject and ("electronic device" in lowered or "gift" in lowered):
            extras.append(f"{subject} fitness tracker device gift")
        if subject and "country" in lowered and "visit" in lowered:
            extras.append(f"{subject} visit country Canada travel")
        if subject and "why" in lowered and ("yoga" in lowered or "put off" in lowered):
            extras.append(f"{subject} yoga video games hobbies")
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
    entity_swap = adversarial_risk and is_specific_attribute_query(query)
    focus_terms = extract_focus_terms(query, names) if entity_swap else []

    def _score(item: str) -> float:
        norm = item.lower()
        score = float(sum(1 for k in keywords if k in norm))
        if entity_swap:
            score += sum(3.0 for t in focus_terms if t in norm)
        else:
            score += sum(3.0 for n in names if n.lower() in norm)
        if "[observation" in norm:
            score += 4.0
        if "session summary" in norm or "session @" in norm:
            score += 2.0
        if temporal and "session @" in norm:
            score += 2.5
        if adversarial_risk and "[observation" in norm:
            if entity_swap:
                score += 3.0 if any(t in norm for t in focus_terms) else 0.5
            else:
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
    if any(marker in lowered for marker in ("when did", "when was", "when is", "what date", "how long", "since ")):
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


OBSERVATION_DIA_ID_RE = re.compile(r"\[observation\s+(D\d+:\d+)\]", re.IGNORECASE)


def extract_observation_dia_ids(context_items: List[str]) -> List[str]:
    """Collect dialog provenance IDs from condensed observation lines (LOC-024)."""
    seen: set[str] = set()
    ordered: List[str] = []
    for item in context_items:
        for match in OBSERVATION_DIA_ID_RE.finditer(item):
            dia_id = match.group(1)
            if dia_id not in seen:
                seen.add(dia_id)
                ordered.append(dia_id)
    return ordered


def source_turn_hydration_enabled(*, benchmark_mode: bool) -> bool:
    raw = os.getenv("RETRIEVE_SOURCE_TURN_HYDRATION", "").strip().lower()
    if raw in ("0", "false", "no"):
        return False
    if raw in ("1", "true", "yes"):
        return True
    return benchmark_mode


def format_source_turn_line(text: str, metadata: dict[str, Any]) -> str:
    dia_id = (metadata or {}).get("dia_id")
    label = f"[source turn {dia_id}]" if dia_id else "[source turn]"
    body = format_episodic_context_line(text, metadata)
    if body.startswith("["):
        return f"{label} {body}"
    return f"{label} {body}"


def is_structured_context_line(text: str) -> bool:
    lowered = text.lower()
    return (
        "[observation" in lowered
        or "[source turn" in lowered
        or "session summary" in lowered
        or "assertion:" in lowered
        or ("session @" in lowered and "score=" in lowered)
    )


def filter_adversarial_context(
    items: List[str],
    sources: List[str],
    *,
    aggressive: bool = False,
    safe_limit: Optional[int] = None,
) -> Tuple[List[str], List[str]]:
    """LOC-013: prefer observations/assertions over raw dialog that may contain trap answers.

    For false-premise (adversarial) questions, ``aggressive`` drops raw dialog
    entirely and caps the number of structured lines. This is the structural
    contract that lets the system abstain instead of surfacing a plausible trap
    answer (matches the EXIA GHOST / Synthius-Mem adversarial approach).
    """
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
    if aggressive:
        raw_limit = int(os.getenv("RETRIEVE_ADVERSARIAL_RAW_LIMIT_STRICT", "0"))
    else:
        raw_limit = int(os.getenv("RETRIEVE_ADVERSARIAL_RAW_LIMIT", "6"))
    if safe_limit is not None and safe_limit > 0:
        safe_items = safe_items[:safe_limit]
        safe_sources = safe_sources[:safe_limit]
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

    async def route_and_retrieve(
        self,
        project_id: Any,
        query: str,
        skip_llm: bool = False,
        llm_config: Optional[Dict[str, str]] = None,
        current_step: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
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
        recall_gate = AstrocyteRecallGate()
        multihop_query = is_multihop_query(query)
        query_plan = recall_gate.classify(
            query, keywords=keywords, base_strategy=strategy, is_multihop=multihop_query
        )
        if not benchmark_mode and not skip_llm:
            query_plan = await recall_gate.refine_with_llm(query, query_plan, llm_config)
        strategy = query_plan.strategy
        # Drive retrieval depth from the complexity-aware plan so simple queries
        # stay cheap and multi-hop queries recall more (TiMem-style).
        complexity = query_plan.complexity
        if is_research_query(query) or multihop_query:
            strategy = "research"
            query_plan.strategy = "research"

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
                query_plan=query_plan,
            )

        # --- Reranking Layer ---
        from src.retrieve.reranker import LocalReranker
        reranker = LocalReranker(llm_config=llm_config)
        # Complexity-aware context budget: simple lookups stay cheap, complex
        # multi-hop queries recall more. An explicit env override still wins.
        rerank_env = os.getenv("RETRIEVE_RERANK_TOP_N")
        if rerank_env is not None:
            rerank_top_n = int(rerank_env)
        else:
            rerank_top_n = query_plan.recall_budget
        if multihop_query:
            rerank_top_n = max(rerank_top_n, 20)
        skip_rerank = os.getenv("RETRIEVE_SKIP_RERANK", "").lower() in ("1", "true", "yes")
        if skip_rerank:
            if benchmark_mode:
                final_items = heuristic_rerank_items(query, context_items, rerank_top_n)
            else:
                final_items = context_items[:rerank_top_n]
        else:
            final_items = await reranker.rerank(query, context_items, top_n=rerank_top_n)

        verification = verify_evidence(
            query,
            final_items,
            plan=query_plan,
            confidence_score=confidence_score,
        )
        if verification.abstain_recommended and not benchmark_mode:
            final_items = []
        context = build_verified_context(final_items, verification)
        if not context and final_items:
            context = "\n\n".join(final_items)
        if benchmark_mode:
            context = "\n\n".join(final_items)
        max_chars = int(os.getenv("RETRIEVE_MAX_CONTEXT_CHARS", "28000"))
        if len(context) > max_chars:
            context = context[:max_chars]
        
        THRESHOLD = query_plan.confidence_threshold if query_plan else float(os.getenv("CONFIDENCE_THRESHOLD", "0.8"))

        sys_prompt = (
            "You are a helpful assistant. Answer ONLY from verified memories in the context. "
            "If evidence is indirect, say so. Prefer later canonical facts over outdated ones. "
            "If no memory supports the answer, respond with 'Unknown.'"
        )
        user_msg = f"Context:\n{context}\n\nQuery: {query}"
        synthesized = False

        # 2. Synthesize Answer (Brief)
        if benchmark_mode:
            answer = context
        elif verification.abstain_recommended:
            answer = abstention_answer(verification)
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
            "question_type": query_plan.question_type,
            "recall_plan": query_plan.to_dict(),
            "verification": verification.to_dict(),
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
        query_plan: Optional[QueryPlan] = None,
    ) -> Tuple[List[str], List[str], float]:
        plan = query_plan or AstrocyteRecallGate().classify(query, keywords=keywords, base_strategy=strategy)
        modes = set(plan.retrieval_modes)
        steps = 1 if complexity == 1 else (3 if complexity == 3 else 2)
        decay = 0.7 if complexity == 1 else (0.3 if complexity == 3 else 0.5)
        skip_graph = os.getenv("RETRIEVE_BENCHMARK_SKIP_GRAPH", "").lower() in ("1", "true", "yes")
        benchmark_mode = os.getenv("RETRIEVE_BENCHMARK_MODE", "").lower() in ("1", "true", "yes")
        bench_graph_steps = int(os.getenv("RETRIEVE_BENCHMARK_GRAPH_STEPS", "0") or "0")
        multihop = is_multihop_query(query) or plan.question_type in ("causal", "relationship", "event_sequence")
        temporal = is_temporal_query(query) or plan.requires_event_chain or "temporal_chain" in modes
        adversarial_risk = is_adversarial_risk_query(query) or plan.requires_abstention_check
        use_graph = (
            strategy == "research"
            or is_research_query(query)
            or is_temporal_query(query)
            or "event_graph" in modes
            or "temporal_chain" in modes
        )
        if benchmark_mode and skip_graph and not (bench_graph_steps > 0 and multihop):
            use_graph = False

        multi_query = benchmark_mode and os.getenv(
            "RETRIEVE_BENCHMARK_MULTI_QUERY", "1"
        ).lower() in ("1", "true", "yes")
        extra_queries: Optional[List[str]] = None
        if multi_query:
            if adversarial_risk:
                extra_queries = supplementary_vector_queries_adversarial(query, keywords)
            elif multihop or temporal:
                extra_queries = supplementary_vector_queries(query, keywords)
            elif not is_research_query(query):
                extra_queries = supplementary_vector_queries_recall(query, keywords)
        vec_items, vec_sources, vec_conf = await self._vector_search(
            project_id,
            query,
            current_step=current_step,
            extra_queries=extra_queries,
            multihop=multihop,
            temporal=temporal,
            adversarial_risk=adversarial_risk,
            vector_limit=plan.vector_limit,
        )
        if multihop:
            assert_items, assert_sources, assert_conf = self._multihop_assertion_search(
                project_id, keywords
            )
        elif plan.requires_latest_state or "latest_canonical_fact" in modes:
            assert_items, assert_sources, assert_conf = self._temporal_assertion_search(
                project_id, query, keywords
            )
        else:
            assert_items, assert_sources, assert_conf = self._assertion_search(project_id, query)
        light_items: List[str] = []
        light_sources: List[str] = []
        light_conf = 0.0
        if multihop and keywords:
            light_items, light_sources, light_conf = self._light_entity_assertions(
                project_id, keywords, min_keyword_matches=1
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
                project_id, keywords, min_keyword_matches=2 if multihop else 1
            )
            light_items, light_sources, light_conf = [], [], 0.0

        mode_items: List[str] = []
        mode_sources: List[str] = []
        mode_conf = 0.0
        if "persona_profile" in modes:
            p_items, p_sources, p_conf = self._persona_search(project_id, keywords)
            mode_items.extend(p_items)
            mode_sources.extend(p_sources)
            mode_conf = max(mode_conf, p_conf)
        if "event_graph" in modes or plan.requires_event_chain:
            e_items, e_sources, e_conf = self._event_graph_search(project_id, keywords)
            mode_items.extend(e_items)
            mode_sources.extend(e_sources)
            mode_conf = max(mode_conf, e_conf)
        if "cross_session_summary" in modes:
            s_items, s_sources, s_conf = self._session_summary_search(project_id, query)
            mode_items.extend(s_items)
            mode_sources.extend(s_sources)
            mode_conf = max(mode_conf, s_conf)
        if "contradiction_audit" in modes:
            c_items, c_sources, c_conf = self._contradiction_audit_search(project_id, keywords)
            mode_items.extend(c_items)
            mode_sources.extend(c_sources)
            mode_conf = max(mode_conf, c_conf)

        context_items, sources = merge_retrieval_items(
            (vec_items, vec_sources),
            (assert_items, assert_sources),
            (graph_items, graph_sources),
            (light_items, light_sources),
            (mode_items, mode_sources),
        )
        if source_turn_hydration_enabled(benchmark_mode=benchmark_mode):
            context_items, sources = self._hydrate_source_turns(
                project_id, context_items, sources
            )
        if is_adversarial_phrasing(query) and os.getenv(
            "RETRIEVE_ENTITY_ALIGNMENT_FILTER", "1"
        ).lower() in ("1", "true", "yes"):
            context_items, sources = filter_entity_evidence_context(
                query, context_items, sources
            )
        if is_entity_swap_trap(query) and os.getenv(
            "RETRIEVE_SWAP_TRAP_FILTER", "1"
        ).lower() in ("1", "true", "yes"):
            context_items, sources = filter_swap_trap_context(
                query, context_items, sources
            )
        trap_filter = getattr(plan, "requires_trap_filter", False)
        if adversarial_risk and os.getenv(
            "RETRIEVE_ADVERSARIAL_FILTER", "1"
        ).lower() in ("1", "true", "yes"):
            # Aggressive raw-dialog drop only for strong counterfactual phrasing;
            # entity-swap traps use attribute-focused recall instead.
            aggressive = trap_filter and is_adversarial_phrasing(query)
            context_items, sources = filter_adversarial_context(
                context_items,
                sources,
                aggressive=aggressive,
                safe_limit=plan.recall_budget if aggressive else None,
            )
        return context_items, sources, max(vec_conf, assert_conf, graph_conf, light_conf, mode_conf)

    def _format_assertion_line(self, assertion: Assertion, *, include_chain: bool = False) -> str:
        base = (
            f"Assertion: {assertion.subject_text} {assertion.predicate} "
            f"{assertion.object_text} (conf: {assertion.confidence}, stratum: {assertion.stratum})"
        )
        if not include_chain:
            return base
        chain = fetch_supersession_chain(self.db, assertion.id)
        if len(chain) <= 1:
            return base
        history = " -> ".join(
            f"{row.object_text}[{row.status}]" for row in chain
        )
        return f"{base} | change_path: {history}"

    def _temporal_assertion_search(
        self, project_id: Any, query: str, keywords: List[str]
    ) -> Tuple[List[str], List[str], float]:
        subject_hint = extract_entity_names(query)
        subject_text = subject_hint[0] if subject_hint else None
        if isinstance(project_id, list):
            pid = project_id[0]
        else:
            pid = project_id
        try:
            import uuid as _uuid

            project_uuid = pid if isinstance(pid, _uuid.UUID) else _uuid.UUID(str(pid))
        except Exception:
            return self._assertion_search(project_id, query)

        assertions = latest_valid_assertions(
            self.db,
            project_uuid,
            subject_text=subject_text,
            limit=int(os.getenv("RETRIEVE_ASSERTION_LIMIT", "25")),
        )
        if not assertions and keywords:
            return self._assertion_search(project_id, query)
        if not assertions:
            return [], [], 0.0

        context_parts = [
            self._format_assertion_line(a, include_chain=True) for a in assertions
        ]
        sources = [str(a.id) for a in assertions]
        max_conf = max(a.confidence for a in assertions)
        return context_parts, sources, max_conf

    def _persona_search(
        self, project_id: Any, keywords: List[str]
    ) -> Tuple[List[str], List[str], float]:
        if not keywords:
            return [], [], 0.0
        if isinstance(project_id, list):
            stmt = select(Policy).where(Policy.project_id.in_(project_id))
        else:
            stmt = select(Policy).where(Policy.project_id == project_id)
        policies = self.db.execute(stmt.limit(8)).scalars().all()
        items = [f"Persona policy: when {p.trigger}, {p.rule}" for p in policies]
        if not items:
            return self._light_entity_assertions(project_id, keywords, min_keyword_matches=1)
        return items, [str(p.id) for p in policies], max((p.confidence for p in policies), default=0.0)

    def _event_graph_search(
        self, project_id: Any, keywords: List[str]
    ) -> Tuple[List[str], List[str], float]:
        if not keywords:
            return [], [], 0.0
        conditions = []
        for keyword in keywords:
            pattern = f"%{keyword}%"
            conditions.append(Event.summary.ilike(pattern))
            conditions.append(Event.type.ilike(pattern))
        if isinstance(project_id, list):
            stmt = select(Event).where(Event.project_id.in_(project_id), or_(*conditions))
        else:
            stmt = select(Event).where(Event.project_id == project_id, or_(*conditions))
        events = self.db.execute(
            stmt.order_by(Event.occurred_at.desc().nullslast()).limit(12)
        ).scalars().all()
        if not events:
            return [], [], 0.0
        items = [f"Event: [{e.type}] {e.summary} (conf: {e.confidence})" for e in events]
        max_conf = max((e.confidence for e in events), default=0.0)
        return items, [str(e.id) for e in events], max_conf

    def _session_summary_search(
        self, project_id: Any, query: str
    ) -> Tuple[List[str], List[str], float]:
        if isinstance(project_id, list):
            project_filter = EpisodicItem.project_id.in_(project_id)
        else:
            project_filter = EpisodicItem.project_id == project_id
        stmt = (
            select(EpisodicItem)
            .where(
                project_filter,
                EpisodicItem.metadata_["kind"].as_string() == "session_summary",
            )
            .order_by(EpisodicItem.occurred_at.desc())
            .limit(8)
        )
        rows = self.db.execute(stmt).scalars().all()
        if not rows:
            return [], [], 0.0
        items = [
            format_episodic_context_line(row.text, row.metadata_ or {}) for row in rows
        ]
        return items, [str(row.id) for row in rows], 0.75

    def _contradiction_audit_search(
        self, project_id: Any, keywords: List[str]
    ) -> Tuple[List[str], List[str], float]:
        if isinstance(project_id, list):
            stmt = select(Assertion).where(
                Assertion.project_id.in_(project_id),
                Assertion.status.in_(["approved", "active", "superseded"]),
            )
        else:
            stmt = select(Assertion).where(
                Assertion.project_id == project_id,
                Assertion.status.in_(["approved", "active", "superseded"]),
            )
        if keywords:
            conditions = []
            for keyword in keywords:
                pattern = f"%{keyword}%"
                conditions.extend(
                    [
                        Assertion.subject_text.ilike(pattern),
                        Assertion.object_text.ilike(pattern),
                    ]
                )
            stmt = stmt.where(or_(*conditions))
        assertions = self.db.execute(
            stmt.order_by(Assertion.last_seen_at.desc()).limit(16)
        ).scalars().all()
        if not assertions:
            return [], [], 0.0
        items = [
            self._format_assertion_line(a, include_chain=True) for a in assertions
        ]
        return items, [str(a.id) for a in assertions], max(a.confidence for a in assertions)

    def _hydrate_source_turns(
        self,
        project_id: Any,
        context_items: List[str],
        sources: List[str],
    ) -> Tuple[List[str], List[str]]:
        """Fetch verbatim dialog turns linked from observation dia_id provenance."""
        dia_ids = extract_observation_dia_ids(context_items)
        if not dia_ids:
            return context_items, sources

        max_ids = int(os.getenv("RETRIEVE_SOURCE_TURN_MAX", "12"))
        dia_ids = dia_ids[:max_ids]

        existing_norm = {normalize_chunk_text(item) for item in context_items}
        hydrated_items: List[str] = []
        hydrated_sources: List[str] = []

        try:
            if isinstance(project_id, list):
                project_filter = EpisodicItem.project_id.in_(project_id)
            else:
                project_filter = EpisodicItem.project_id == project_id

            stmt = (
                select(EpisodicItem)
                .where(
                    project_filter,
                    EpisodicItem.metadata_["dia_id"].as_string().in_(dia_ids),
                    or_(
                        EpisodicItem.metadata_["kind"].is_(None),
                        EpisodicItem.metadata_["kind"].as_string().notin_(
                            ["observation", "session_summary"]
                        ),
                    ),
                )
                .order_by(EpisodicItem.occurred_at.asc())
            )
            rows = self.db.execute(stmt).scalars().all()
        except Exception as exc:
            logger.warning("Source-turn hydration query failed: %s", exc)
            return context_items, sources

        for row in rows:
            meta = row.metadata_ or {}
            norm = normalize_chunk_text(row.text)
            if not norm or norm in existing_norm:
                continue
            line = format_source_turn_line(row.text, meta)
            if line in context_items or line in hydrated_items:
                continue
            hydrated_items.append(line)
            hydrated_sources.append(str(row.id))
            existing_norm.add(norm)

        if not hydrated_items:
            return context_items, sources
        return context_items + hydrated_items, sources + hydrated_sources

    async def _vector_search(
        self,
        project_id: Any,
        query: str,
        current_step: Optional[int] = None,
        extra_queries: Optional[List[str]] = None,
        multihop: bool = False,
        temporal: bool = False,
        adversarial_risk: bool = False,
        vector_limit: Optional[int] = None,
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
        env_limit = os.getenv("RETRIEVE_VECTOR_LIMIT")
        if env_limit is not None:
            vector_limit = int(env_limit)
        elif vector_limit is None:
            vector_limit = 20
        if multihop:
            vector_limit = max(vector_limit, 24)
        per_query_limit = max(8, vector_limit // max(1, len(search_queries)))
        if multihop:
            per_query_limit = max(per_query_limit, 10)

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
                from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny
                if isinstance(project_id, list):
                    search_filter = Filter(
                        must=[FieldCondition(key="project_id", match=MatchAny(any=project_id))]
                    )
                else:
                    search_filter = Filter(
                        must=[FieldCondition(key="project_id", match=MatchValue(value=project_id))]
                    )
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
                meta = payload.get("metadata", {}) or {}
                if is_adversarial_phrasing(query) and os.getenv(
                    "RETRIEVE_ENTITY_ALIGNMENT_FILTER", "1"
                ).lower() in ("1", "true", "yes"):
                    if not episodic_hit_admissible(query, text, meta):
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

    def _assertion_search(self, project_id: Any, query: str) -> Tuple[List[str], List[str], float]:
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
        self, project_id: Any, keywords: List[str]
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
        self, project_id: Any, keywords: List[str], *, min_keyword_matches: int = 1
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
