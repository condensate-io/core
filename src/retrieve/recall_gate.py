"""Astrocyte Recall Gate — pre-retrieval memory routing for LoCoMo-style queries."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional

QuestionType = Literal[
    "exact_fact",
    "temporal_update",
    "preference",
    "relationship",
    "event_sequence",
    "causal",
    "cross_session_summary",
    "contradiction",
    "multimodal",
    "abstention",
]

MemoryScope = Literal["single_session", "cross_session", "global"]
RetrievalMode = Literal[
    "latest_canonical_fact",
    "temporal_chain",
    "persona_profile",
    "event_graph",
    "contradiction_audit",
    "cross_session_summary",
    "multimodal_memory",
    "abstention_check",
]

QUESTION_TYPE_TO_MODES: dict[str, list[str]] = {
    "exact_fact": ["latest_canonical_fact"],
    "temporal_update": ["temporal_chain", "latest_canonical_fact", "abstention_check"],
    "preference": ["persona_profile", "latest_canonical_fact", "temporal_chain"],
    "relationship": ["persona_profile", "event_graph"],
    "event_sequence": ["event_graph", "temporal_chain"],
    "causal": ["event_graph", "temporal_chain", "latest_canonical_fact"],
    "cross_session_summary": ["cross_session_summary", "persona_profile"],
    "contradiction": ["contradiction_audit", "latest_canonical_fact", "abstention_check"],
    "multimodal": ["multimodal_memory", "latest_canonical_fact"],
    "abstention": ["abstention_check", "latest_canonical_fact"],
}


@dataclass
class QueryPlan:
    question_type: str
    requires_latest_state: bool
    requires_event_chain: bool
    requires_persona: bool
    requires_abstention_check: bool
    memory_scope: str
    confidence_threshold: float
    retrieval_modes: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    strategy: str = "recall"
    # Complexity-aware recall (TiMem/SimpleMem-style adaptive depth):
    # 1 = simple/exact, 2 = medium, 3 = complex/multi-hop. Drives retrieval
    # breadth and final context budget so simple queries stay cheap and
    # complex queries recall more evidence.
    complexity: int = 2
    recall_budget: int = 14
    vector_limit: int = 20
    assertion_limit: int = 25
    # Adversarial / false-premise handling: when true, the router applies
    # aggressive trap filtering and prefers abstention over fabrication.
    requires_trap_filter: bool = False
    # Entity-swap traps (wrong possessive subject) use attribute-focused recall.
    requires_entity_swap: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _has_temporal_markers(query: str) -> bool:
    lowered = query.lower()
    if any(
        marker in lowered
        for marker in (
            "when did",
            "when was",
            "when is",
            "what date",
            "how long",
            "since ",
            "before ",
            "after ",
            "eventually",
            "change",
            "changed",
            "still ",
            "now ",
            "latest",
            "currently",
        )
    ):
        return True
    return bool(re.search(r"\b(19|20)\d{2}\b", query))


def _has_preference_markers(query: str) -> bool:
    lowered = query.lower()
    return any(
        marker in lowered
        for marker in (
            "prefer",
            "favorite",
            "favourite",
            "like to",
            "likes to",
            "enjoy",
            "usually",
            "typically",
        )
    )


def _has_relationship_markers(query: str) -> bool:
    lowered = query.lower()
    return any(
        marker in lowered
        for marker in (
            "relationship",
            "married",
            "dating",
            "friend",
            "partner",
            "family",
            "mother",
            "father",
            "sibling",
            "colleague",
            "personality",
            "describe ",
        )
    )


def _has_causal_markers(query: str) -> bool:
    lowered = query.lower()
    return any(
        marker in lowered
        for marker in (
            "because",
            "why did",
            "cause",
            "led to",
            "result",
            "due to",
            "if ",
            "would ",
            "likely",
        )
    )


def _has_summary_markers(query: str) -> bool:
    lowered = query.lower()
    return any(
        marker in lowered
        for marker in (
            "summarize",
            "summary",
            "overall",
            "in general",
            "across sessions",
            "main theme",
            "what happened between",
        )
    )


def _has_multimodal_markers(query: str) -> bool:
    lowered = query.lower()
    return any(
        marker in lowered
        for marker in (
            "photo",
            "picture",
            "image",
            "video",
            "screenshot",
            "shown",
            "posted",
        )
    )


def _has_abstention_markers(query: str) -> bool:
    lowered = query.lower()
    return any(
        marker in lowered
        for marker in (
            "if she hadn't",
            "if he hadn't",
            "would have",
            "hypothetical",
            "never mentioned",
            "not mentioned",
            "unknown",
        )
    )


def _has_contradiction_markers(query: str) -> bool:
    lowered = query.lower()
    return any(
        marker in lowered
        for marker in (
            "still ",
            "anymore",
            "no longer",
            "instead",
            "contradict",
            "actually",
            "used to",
        )
    )


def _has_event_sequence_markers(query: str) -> bool:
    lowered = query.lower()
    return any(
        marker in lowered
        for marker in (
            "first ",
            "then ",
            "after that",
            "before ",
            "sequence",
            "order of",
            "what happened",
        )
    )


def is_adversarial_phrasing(query: str) -> bool:
    """Detect false-premise / adversarial questions (LoCoMo category 5).

    Adversarial questions presuppose facts that may never have been stated.
    The correct behaviour is to abstain rather than surface a plausible trap
    answer, so we flag these for aggressive trap filtering.

    This intentionally fires only on *strong* signals (counterfactuals and
    explicit presuppositions). Weak speculative phrasing like "would ...
    likely" is left to multi-hop inference, which needs more evidence rather
    than tighter recall.
    """
    lowered = query.lower()
    counterfactual = (
        "if she hadn't",
        "if he hadn't",
        "if they hadn't",
        "hadn't",
        "had not",
        "would have",
        "hypothetical",
        "never mentioned",
        "not mentioned",
    )
    if any(marker in lowered for marker in counterfactual):
        return True
    # Counterfactual conditional: "would ... if ..." (e.g. "what would X do if Y").
    if "would " in lowered and " if " in lowered:
        return True
    # False-premise framings that presuppose unstated plans/feelings.
    presuppositions = (
        "with respect to",
        "plans for",
        "plans to",
        "still want",
        "still planning",
        "still going to",
    )
    if any(marker in lowered for marker in presuppositions):
        return True
    return False


def classify_question_type(query: str) -> str:
    """Deterministic question-type classifier (no LLM)."""
    lowered = query.lower()

    if _has_abstention_markers(query) or (
        "would " in lowered and ("if " in lowered or "likely" in lowered)
    ):
        return "abstention"
    if _has_multimodal_markers(query):
        return "multimodal"
    if _has_summary_markers(query):
        return "cross_session_summary"
    if _has_contradiction_markers(query) and _has_temporal_markers(query):
        return "contradiction"
    if _has_causal_markers(query) and not _has_temporal_markers(query):
        return "causal"
    if _has_event_sequence_markers(query):
        return "event_sequence"
    if _has_preference_markers(query):
        return "preference"
    if _has_relationship_markers(query):
        return "relationship"
    if _has_temporal_markers(query):
        return "temporal_update"
    return "exact_fact"


def _memory_scope_for(query: str, question_type: str) -> str:
    lowered = query.lower()
    if question_type in ("cross_session_summary", "temporal_update", "contradiction", "causal"):
        return "cross_session"
    if "this session" in lowered or "today" in lowered:
        return "single_session"
    return "cross_session"


def _confidence_threshold(question_type: str) -> float:
    thresholds = {
        "exact_fact": 0.65,
        "temporal_update": 0.72,
        "preference": 0.70,
        "relationship": 0.68,
        "event_sequence": 0.70,
        "causal": 0.74,
        "cross_session_summary": 0.66,
        "contradiction": 0.75,
        "multimodal": 0.70,
        "abstention": 0.78,
    }
    return thresholds.get(question_type, 0.72)


def _strategy_for(question_type: str, base_strategy: str) -> str:
    if question_type in (
        "causal",
        "event_sequence",
        "cross_session_summary",
        "temporal_update",
        "relationship",
        "contradiction",
        "abstention",
    ):
        return "research"
    if question_type in ("exact_fact", "preference", "multimodal"):
        return "recall"
    return base_strategy


# Complexity-aware recall. Tier 2 is the baseline (matches the prior fixed
# depth, so we never *reduce* retrieval below the known-good configuration);
# tier 3 expands graph hops / vector pool / context for genuinely complex
# multi-hop and causal queries (TiMem/SimpleMem adaptive depth). We do not use
# tier 1 for any question type — earlier experiments showed that cutting graph
# traversal steps for "simple" questions starved single-hop/temporal recall.
_COMPLEXITY_BY_TYPE = {
    "exact_fact": 2,
    "preference": 2,
    "multimodal": 2,
    "temporal_update": 2,
    "relationship": 2,
    "contradiction": 2,
    "abstention": 2,
    "cross_session_summary": 3,
    "event_sequence": 3,
    "causal": 3,
}

# (recall_budget, vector_limit, assertion_limit) per complexity tier.
# Tier 2 mirrors the prior baseline (budget 16, vector 20); tier 3 expands for
# multi-hop recall without exploding tokens.
_BUDGET_BY_COMPLEXITY = {
    1: (16, 20, 25),
    2: (16, 20, 25),
    3: (20, 24, 30),
}


def _complexity_for(question_type: str, *, is_multihop: bool, is_adversarial: bool) -> int:
    base = _COMPLEXITY_BY_TYPE.get(question_type, 2)
    if is_adversarial:
        # Adversarial questions keep baseline retrieval depth (so context is
        # not starved) but the budget is tightened separately and trap
        # filtering is applied. Never below tier 2.
        return min(max(base, 2), 2)
    if is_multihop:
        return 3
    return base


def build_query_plan(
    query: str,
    *,
    keywords: Optional[List[str]] = None,
    base_strategy: str = "recall",
    is_multihop: bool = False,
) -> QueryPlan:
    """Build a structured retrieval plan from a user question."""
    question_type = classify_question_type(query)
    modes = list(QUESTION_TYPE_TO_MODES.get(question_type, ["latest_canonical_fact"]))
    scope = _memory_scope_for(query, question_type)

    from src.retrieve.entity_alignment import (
        is_adversarial_risk_query,
        is_specific_attribute_query,
    )

    adversarial_risk = is_adversarial_risk_query(query)
    strong_trap = is_adversarial_phrasing(query)
    entity_swap = is_specific_attribute_query(query)
    complexity = _complexity_for(
        question_type, is_multihop=is_multihop, is_adversarial=strong_trap
    )
    recall_budget, vector_limit, assertion_limit = _BUDGET_BY_COMPLEXITY[complexity]
    if strong_trap:
        # Tighten budget only for explicit counterfactual / presupposition phrasing.
        recall_budget = min(recall_budget, 8)

    if "contradiction_audit" not in modes and adversarial_risk:
        modes = modes + ["abstention_check"] if "abstention_check" not in modes else modes

    return QueryPlan(
        question_type=question_type,
        requires_latest_state=question_type
        in ("exact_fact", "temporal_update", "preference", "contradiction", "causal"),
        requires_event_chain=question_type
        in ("temporal_update", "event_sequence", "causal", "contradiction"),
        requires_persona=question_type in ("preference", "relationship", "cross_session_summary"),
        requires_abstention_check=question_type in ("abstention", "contradiction", "temporal_update")
        or adversarial_risk,
        memory_scope=scope,
        confidence_threshold=_confidence_threshold(question_type),
        retrieval_modes=modes,
        keywords=list(keywords or []),
        strategy=_strategy_for(question_type, base_strategy),
        complexity=complexity,
        recall_budget=recall_budget,
        vector_limit=vector_limit,
        assertion_limit=assertion_limit,
        requires_trap_filter=strong_trap,
        requires_entity_swap=entity_swap,
    )


class AstrocyteRecallGate:
    """Pre-retrieval gate that routes queries into memory pathways."""

    def classify(
        self,
        query: str,
        *,
        keywords: Optional[List[str]] = None,
        base_strategy: str = "recall",
        is_multihop: bool = False,
    ) -> QueryPlan:
        return build_query_plan(
            query,
            keywords=keywords,
            base_strategy=base_strategy,
            is_multihop=is_multihop,
        )

    async def refine_with_llm(
        self,
        query: str,
        plan: QueryPlan,
        llm_config: Optional[Dict[str, str]] = None,
    ) -> QueryPlan:
        """Optional LLM refinement for interactive (non-benchmark) use."""
        from src.retrieve.router import get_current_client

        prompt = f"""Classify this memory query for retrieval routing.

Query: {query}
Current classification: {plan.question_type}

Return JSON with optional overrides:
{{
  "question_type": "{plan.question_type}" | one of exact_fact, temporal_update, preference, relationship, event_sequence, causal, cross_session_summary, contradiction, multimodal, abstention,
  "confidence_threshold": float between 0.5 and 0.9
}}"""
        try:
            client, model = get_current_client(llm_config)
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            import json

            data = json.loads(response.choices[0].message.content)
            qtype = data.get("question_type", plan.question_type)
            if qtype in QUESTION_TYPE_TO_MODES:
                plan.question_type = qtype
                plan.retrieval_modes = list(QUESTION_TYPE_TO_MODES[qtype])
            if "confidence_threshold" in data:
                plan.confidence_threshold = float(data["confidence_threshold"])
            plan.strategy = _strategy_for(plan.question_type, plan.strategy)
        except Exception:
            pass
        return plan
