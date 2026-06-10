"""Astrocyte Evidence Verifier — post-retrieval support and abstention checks."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from src.retrieve.recall_gate import QueryPlan


@dataclass
class VerificationResult:
    answerable: bool
    support_level: str
    temporal_validity: str
    contradiction_found: bool
    missing_evidence: List[str] = field(default_factory=list)
    required_citations: List[str] = field(default_factory=list)
    abstain_recommended: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_DIA_ID_RE = re.compile(r"\bD\d+:\d+\b", re.IGNORECASE)


def _extract_dia_ids(items: List[str]) -> List[str]:
    found: List[str] = []
    seen: set[str] = set()
    for item in items:
        for match in _DIA_ID_RE.findall(item):
            key = match.upper()
            if key not in seen:
                seen.add(key)
                found.append(key)
    return found


def _keyword_coverage(query: str, context_items: List[str]) -> float:
    from src.retrieve.router import extract_query_keywords, normalize_chunk_text

    keywords = extract_query_keywords(query)
    if not keywords:
        return 0.0
    blob = " ".join(normalize_chunk_text(item) for item in context_items)
    hits = sum(1 for kw in keywords if kw in blob)
    return hits / len(keywords)


def _has_superseded_markers(items: List[str]) -> bool:
    blob = " ".join(items).lower()
    return any(
        marker in blob
        for marker in ("superseded", "valid_until", "no longer", "used to", "changed to")
    )


def _has_contradiction_markers(items: List[str]) -> bool:
    blob = " ".join(items).lower()
    positive = ("approved", "active", "prefers", "likes", "is ")
    negative = ("not ", "no longer", "rejected", "negated", "instead")
    return any(p in blob for p in positive) and any(n in blob for n in negative)


def verify_evidence(
    query: str,
    context_items: List[str],
    *,
    plan: Optional[QueryPlan] = None,
    confidence_score: float = 0.0,
) -> VerificationResult:
    """Verify whether retrieved context supports answering the query."""
    from src.retrieve.router import extract_query_keywords

    if not context_items:
        abstain = plan.requires_abstention_check if plan else False
        return VerificationResult(
            answerable=False,
            support_level="none",
            temporal_validity="unknown",
            contradiction_found=False,
            missing_evidence=list(extract_query_keywords(query)),
            required_citations=[],
            abstain_recommended=True if abstain or not context_items else False,
        )

    coverage = _keyword_coverage(query, context_items)
    citations = _extract_dia_ids(context_items)
    threshold = plan.confidence_threshold if plan else 0.72
    contradiction = _has_contradiction_markers(context_items)
    outdated = _has_superseded_markers(context_items) and (
        plan is not None and plan.requires_latest_state
    )

    if coverage >= 0.75 and confidence_score >= threshold:
        support = "direct"
        answerable = True
    elif coverage >= 0.45 or confidence_score >= threshold * 0.85:
        support = "indirect"
        answerable = True
    else:
        support = "none"
        answerable = False

    temporal_validity = "latest"
    if outdated or contradiction:
        temporal_validity = "outdated"
    elif plan and plan.requires_latest_state:
        temporal_validity = "latest"

    missing: List[str] = []
    if coverage < 0.45:
        missing = [kw for kw in extract_query_keywords(query) if kw not in " ".join(context_items).lower()]

    abstain = False
    if plan and plan.requires_abstention_check:
        if support == "none" or (contradiction and not outdated):
            abstain = True
    if not answerable and plan and plan.question_type == "abstention":
        abstain = True
    if confidence_score < threshold * 0.5 and plan and plan.requires_abstention_check:
        abstain = True

    return VerificationResult(
        answerable=answerable and not abstain,
        support_level=support,
        temporal_validity=temporal_validity,
        contradiction_found=contradiction,
        missing_evidence=missing,
        required_citations=citations[:8],
        abstain_recommended=abstain,
    )


def build_verified_context(context_items: List[str], verification: VerificationResult) -> str:
    """Format context for answer synthesis with verification metadata."""
    if verification.abstain_recommended:
        return ""
    header = (
        f"[Verified support={verification.support_level}; "
        f"temporal={verification.temporal_validity}; "
        f"citations={','.join(verification.required_citations) or 'none'}]"
    )
    body = "\n\n".join(context_items)
    return f"{header}\n\n{body}"


def abstention_answer(verification: VerificationResult) -> str:
    if verification.contradiction_found and verification.temporal_validity == "outdated":
        return "I cannot determine a single supported answer because retrieved memories conflict or are outdated."
    if verification.missing_evidence:
        return "I do not have sufficient verified memory to answer this question."
    return "Unknown."
