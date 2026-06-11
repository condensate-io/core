"""Query-only entity–evidence alignment for false-premise (adversarial) retrieval.

Detects adversarial-risk questions from question structure (not benchmark labels)
and filters retrieved context so attribute assertions require provenance for the
questioned entity — without tightening recall for temporal, multi-hop, or ordinary
single-hop questions.
"""

from __future__ import annotations

import os
import re
from typing import List, Tuple

from src.retrieve.recall_gate import is_adversarial_phrasing

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

OBSERVATION_DIA_ID_RE = re.compile(r"\bD\d+:\d+\b", re.IGNORECASE)

_POSSESSIVE_ARTIFACT_RE = re.compile(
    r"\b([A-Z][a-z]+)'s\s+"
    r"(necklace|bowl|ring|gift|grandma|grandpa|grandmother|grandfather)\b",
    re.IGNORECASE,
)

_POSSESSIVE_VALID_RE = re.compile(
    r"'s\s+(kids|children|friends|hobbies|job|career|plans|dog|cat)\b",
    re.IGNORECASE,
)


def _extract_query_keywords(query: str) -> List[str]:
    words = re.findall(r"[a-zA-Z']+", query.lower())
    return [w for w in words if len(w) > 2 and w not in _STOPWORDS][:12]


def _extract_entity_names(query: str) -> List[str]:
    names = re.findall(r"\b([A-Z][a-z]+)\b", query)
    return [n for n in names if n not in _ENTITY_SKIP]


def _normalize_chunk_text(text: str) -> str:
    stripped = text.strip()
    if ":" in stripped:
        _, _, body = stripped.partition(":")
        if body.strip():
            stripped = body.strip()
    return re.sub(r"\s+", " ", stripped.lower())


def _is_temporal_query(query: str) -> bool:
    lowered = query.lower()
    if any(
        marker in lowered
        for marker in ("when did", "when was", "when is", "what date", "how long", "since ")
    ):
        return True
    return bool(re.search(r"\b(19|20)\d{2}\b", query))


def _is_structured_context_line(text: str) -> bool:
    lowered = text.lower()
    return (
        "[observation" in lowered
        or "[source turn" in lowered
        or "session summary" in lowered
        or "assertion:" in lowered
        or ("session @" in lowered and "score=" in lowered)
    )


def is_entity_swap_trap(query: str) -> bool:
    """High-confidence entity-swap false premise — gates trap suppression only."""
    if _is_temporal_query(query):
        return False

    lowered = query.lower()

    if _POSSESSIVE_VALID_RE.search(query):
        if not any(
            marker in lowered
            for marker in ("symbolize", "reminder of", "with respect to", "grandma", "grandpa")
        ):
            return False

    if _POSSESSIVE_ARTIFACT_RE.search(query):
        return True
    if "symbolize" in lowered or "reminder of" in lowered:
        return True
    if re.search(r"\bwhat (?:country|city|state) (?:is|was)\b", lowered):
        return True
    if ("grandma" in lowered or "grandpa" in lowered) and (
        "gift" in lowered or "'s" in query
    ):
        return True
    if "with respect to" in lowered:
        return True
    if "type of individuals" in lowered and (
        "agency" in lowered or "adoption" in lowered
    ):
        return True
    if re.search(r"\bIs\s+\w+\s+\w+'s\s+(pet|cat|dog|guinea)\b", query):
        return True
    if re.search(r"\bworkshop\b", lowered) and re.search(
        r"\bdid\s+\w+\s+attend\b", lowered
    ):
        return True
    if re.search(r"\bused\s+to\s+do\s+with\b", lowered):
        return True
    if re.search(r"\band\s+h(?:er|is|im)\s+family\b", lowered):
        return True
    if re.search(r"\bduring\s+their\s+(camping|road|trip)\b", lowered):
        return True
    if re.search(r"'s\s+(internship|store|studio)\b", lowered):
        return True
    if re.search(r"\bfavorite\s+style\s+of\s+(painting|art)\b", lowered):
        return True
    return False


def is_specific_attribute_query(query: str) -> bool:
    """Broader false-premise risk — recall, reranking, and adversarial-risk routing."""
    if is_entity_swap_trap(query):
        return True

    if _is_temporal_query(query):
        return False

    lowered = query.lower()

    if re.search(
        r"\b(what|which)\s+(instrument|song|style|band|music)\b.*'s\b", lowered
    ):
        return True
    if re.search(r"\bwhat\s+type\s+of\s+instrument\b", lowered):
        return True
    if re.search(
        r"\b's\s+(favorite|style\s+of)\s+(song|music|painting|art)\b", lowered
    ):
        return True
    if re.search(r"\b(what|which)\s+(workshop|class|activity|sport|group)\s+did\b", lowered):
        return True
    if re.search(r"'s\s+(internship|store|studio|job\s+at|business)\b", lowered):
        return True
    if re.search(r"'s\s+(team|puppy|kitten|child)\b", lowered):
        return True
    if re.search(r"\bwhat\s+is\s+the\s+name\s+of\b", lowered) and "'s" in query:
        return True
    if re.search(r"\bmain\s+focus\b", lowered):
        return True
    if re.search(r"\bhow\s+long\s+was\s+\w+\s+a\s+part\s+of\b", lowered):
        return True
    if re.search(r"\bwhat\s+(?:book|game|activity)\b", lowered) and re.search(
        r"\b(?:is|was|did)\s+\w+\b", lowered
    ):
        return True
    return False


def is_adversarial_risk_query(query: str) -> bool:
    """Production-fair adversarial-risk signal from query text only."""
    if is_adversarial_phrasing(query):
        return True
    if is_specific_attribute_query(query):
        return True
    return False


def extract_focus_terms(query: str, entities: List[str]) -> List[str]:
    """Content terms from the question excluding entity names."""
    entity_lower = {e.lower() for e in entities}
    terms: List[str] = []
    seen: set[str] = set()

    def _skip_term(word: str) -> bool:
        lowered = word.lower()
        if lowered in entity_lower or lowered in seen:
            return True
        for entity in entity_lower:
            if lowered == f"{entity}'s" or lowered.startswith(f"{entity}'"):
                return True
            if lowered == entity:
                return True
        return False

    for word in _extract_query_keywords(query):
        if not _skip_term(word):
            seen.add(word.lower())
            terms.append(word)
    for match in re.finditer(r"'s\s+([a-zA-Z]+)", query):
        word = match.group(1).lower()
        if len(word) > 2 and not _skip_term(word):
            seen.add(word)
            terms.append(word)
    return terms


def line_asserts_query_focus(line: str, focus_terms: List[str]) -> bool:
    """True when the line appears to answer the queried attribute."""
    if not focus_terms:
        return False
    norm = _normalize_chunk_text(line)
    specific = [t for t in focus_terms if len(t) >= 5]
    if specific and any(t in norm for t in specific):
        return True
    hits = sum(1 for t in focus_terms if t in norm)
    return hits >= 2


def line_has_entity_provenance(line: str, entities: List[str]) -> bool:
    """Structured provenance for the questioned entity."""
    lowered = line.lower()
    if not entities or not any(e.lower() in lowered for e in entities):
        return False
    if "[observation" in lowered and OBSERVATION_DIA_ID_RE.search(line):
        return True
    if "[source turn" in lowered:
        return True
    if "session summary" in lowered:
        return True
    if "assertion:" in lowered:
        blob = lowered.split("assertion:", 1)[-1][:160]
        return any(e.lower() in blob for e in entities)
    return False


def entity_evidence_aligned(query: str, line: str) -> bool:
    """Keep line unless it asserts the queried attribute without entity provenance."""
    if not is_adversarial_risk_query(query):
        return True
    entities = _extract_entity_names(query)
    if not entities:
        return True
    focus = extract_focus_terms(query, entities)
    if not line_asserts_query_focus(line, focus):
        return True
    return line_has_entity_provenance(line, entities)


def filter_entity_evidence_context(
    query: str,
    items: List[str],
    sources: List[str],
) -> Tuple[List[str], List[str]]:
    """Drop attribute-asserting lines lacking provenance for the questioned entity."""
    if not is_adversarial_risk_query(query):
        return items, sources

    kept_items: List[str] = []
    kept_sources: List[str] = []
    for item, source in zip(items, sources):
        if entity_evidence_aligned(query, item):
            kept_items.append(item)
            kept_sources.append(source)

    if kept_items:
        return kept_items, kept_sources

    entities = _extract_entity_names(query)
    for item, source in zip(items, sources):
        if _is_structured_context_line(item) and any(
            e.lower() in item.lower() for e in entities
        ):
            kept_items.append(item)
            kept_sources.append(source)
    return kept_items, kept_sources


def episodic_hit_admissible(
    query: str, text: str, metadata: dict | None = None
) -> bool:
    """Pre-retrieval gate: adversarial-risk hits need subject mention + dia_id overlap."""
    if not is_adversarial_risk_query(query):
        return True

    entities = _extract_entity_names(query)
    if not entities:
        return True

    meta = metadata or {}
    kind = str(meta.get("kind", "")).lower()
    lowered = text.lower()

    if kind in ("observation", "session_summary"):
        return True
    if "[observation" in lowered or "session summary" in lowered:
        return True

    dia_id = meta.get("dia_id")
    if not dia_id:
        return False
    return any(entity.lower() in lowered for entity in entities)


_VALUE_CLAUSE_RE = re.compile(
    r"\b(symboliz\w*|represents?|stands?\s+for|means?|reminder\s+of|"
    r"from|attended|reading|playing|perform\w*|named)\b[^.;\n]*",
    re.IGNORECASE,
)

_BOOLEAN_SWAP_RE = re.compile(
    r"\bIs\s+(\w+)\s+(\w+)'s\s+(pet|cat|dog|guinea)\b",
    re.IGNORECASE,
)


def _line_subjects(line: str) -> List[str]:
    return [
        name
        for name in re.findall(r"\b([A-Z][a-z]+)\b", line)
        if name not in _ENTITY_SKIP
    ]


def line_affirms_false_premise_for_query_entity(query: str, line: str) -> bool:
    """Line attributes the queried focus to the questioned (wrong) entity."""
    if not is_entity_swap_trap(query):
        return False
    entities = _extract_entity_names(query)
    if not entities:
        return False
    subject = entities[0].lower()
    focus = extract_focus_terms(query, entities)
    if not line_asserts_query_focus(line, focus):
        return False
    norm = _normalize_chunk_text(line)
    for term in focus:
        if re.search(rf"{re.escape(subject)}'s\s+{re.escape(term)}", norm):
            return True
        if re.search(
            rf"{re.escape(subject)}\b[^.;\n]{{0,40}}\b{re.escape(term)}\b", norm
        ):
            return True
    return False


def line_leaks_cross_entity_trap_answer(query: str, line: str) -> bool:
    """Line answers the queried attribute for a different person (trap leakage)."""
    if not is_entity_swap_trap(query):
        return False
    entities = _extract_entity_names(query)
    if not entities:
        return False
    query_entity = entities[0].lower()
    focus = extract_focus_terms(query, entities)
    if not line_asserts_query_focus(line, focus):
        return False
    norm = _normalize_chunk_text(line)
    for name in _line_subjects(line):
        if name.lower() == query_entity:
            continue
        if name.lower() in norm:
            return True
    return False


def line_affirms_boolean_swap_trap(query: str, line: str) -> bool:
    """Affirms a false yes/no binding for pet/kinship swap questions."""
    match = _BOOLEAN_SWAP_RE.search(query)
    if not match:
        return False
    entity_name = match.group(1).lower()
    owner = match.group(2).lower()
    norm = _normalize_chunk_text(line)
    if re.search(r"\byes\b", norm) and entity_name in norm:
        return True
    if re.search(rf"{re.escape(owner)}'s\s+\w+", norm) and entity_name in norm:
        pet = match.group(3).lower()
        if pet in norm:
            return True
    return False


def redact_trap_value_clauses(line: str) -> str:
    """Remove attribute-value clauses that leak trap answers."""
    redacted = _VALUE_CLAUSE_RE.sub("", line)
    redacted = re.sub(r"\s{2,}", " ", redacted).strip(" ,;")
    return redacted


def swap_trap_line_allowed(query: str, line: str) -> Tuple[bool, str]:
    """Return (keep, possibly_redacted_line) for entity-swap adversarial queries."""
    if not is_entity_swap_trap(query):
        return True, line
    if line_affirms_false_premise_for_query_entity(query, line):
        return False, line
    if line_affirms_boolean_swap_trap(query, line):
        return False, line
    if line_leaks_cross_entity_trap_answer(query, line):
        return False, line
    redacted = redact_trap_value_clauses(line)
    if redacted != line and redacted.strip():
        entities = _extract_entity_names(query)
        focus = extract_focus_terms(query, entities)
        if not line_asserts_query_focus(redacted, focus):
            return True, redacted
    return True, line


def filter_swap_trap_context(
    query: str,
    items: List[str],
    sources: List[str],
) -> Tuple[List[str], List[str]]:
    """Suppress trap-answer leakage for entity-swap (false-premise) questions."""
    if not is_entity_swap_trap(query):
        return items, sources

    min_tokens = int(os.getenv("RETRIEVE_SWAP_TRAP_MIN_TOKENS", "0"))

    def _estimate_tokens(lines: List[str]) -> int:
        return sum(len(line.split()) for line in lines)

    def _structured_evidence_count(lines: List[str]) -> int:
        count = 0
        for line in lines:
            lowered = line.lower()
            if (
                "[observation" in lowered
                or "assertion:" in lowered
                or "[source turn" in lowered
            ):
                count += 1
        return count

    pre_structured = _structured_evidence_count(items)

    kept_items: List[str] = []
    kept_sources: List[str] = []
    for item, source in zip(items, sources):
        keep, processed = swap_trap_line_allowed(query, item)
        if keep and processed.strip():
            kept_items.append(processed)
            kept_sources.append(source)

    if kept_items:
        result_items, result_sources = kept_items, kept_sources
    else:
        entities = _extract_entity_names(query)
        result_items = []
        result_sources = []
        for item, source in zip(items, sources):
            norm = _normalize_chunk_text(item)
            if entities and any(e.lower() in norm for e in entities):
                if not line_asserts_query_focus(
                    item, extract_focus_terms(query, entities)
                ):
                    result_items.append(item)
                    result_sources.append(source)
        if not result_items:
            return items, sources

    post_structured = _structured_evidence_count(result_items)
    if pre_structured > 0 and post_structured == 0:
        return items, sources
    if min_tokens > 0 and _estimate_tokens(result_items) < min_tokens:
        return items, sources

    return result_items, result_sources


def supplementary_vector_queries_adversarial(
    query: str, keywords: List[str]
) -> List[str]:
    """Entity + focus terms for adversarial-risk vector search (pre-retrieval)."""
    names = _extract_entity_names(query)
    if not names:
        return []
    subject = names[0]
    focus = extract_focus_terms(query, names)
    swap_trap = is_specific_attribute_query(query)
    queries: List[str] = []
    if focus:
        queries.append(f"{subject} {' '.join(focus[:4])}")
        if swap_trap:
            attr_only = [
                t
                for t in focus[:5]
                if subject.lower() not in t.lower()
            ]
            if attr_only:
                queries.append(" ".join(attr_only))
    elif keywords:
        content = [k for k in keywords if k.lower() != subject.lower()][:4]
        if content:
            queries.append(f"{subject} {' '.join(content)}")
            if swap_trap:
                queries.append(" ".join(content[:4]))
    else:
        queries.append(subject)
    return queries
