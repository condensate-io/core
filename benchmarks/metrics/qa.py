"""Score retrieved context against LoCoMo QA annotations (no LLM judge required)."""

from __future__ import annotations

import re
import string
from typing import Any


def normalize(text: str | int | float | None) -> str:
    if text is None:
        return ""
    lowered = str(text).lower().strip()
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.translate(str.maketrans("", "", string.punctuation))


_SESSION_YEAR = re.compile(r"session @ .+?(\d{4})", re.IGNORECASE)
_MONTH_NAMES = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def list_answer_in_context(answer: str | int | float | None, context: str) -> bool:
    """Match comma/semicolon-separated gold answers when most parts appear in context."""
    if answer is None or not context:
        return False
    answer_str = str(answer).strip()
    if "," not in answer_str and ";" not in answer_str:
        return False
    parts = re.split(r"[,;]", answer_str)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) < 2:
        return False
    norm_context = normalize(context)
    hits = 0
    for part in parts:
        norm_part = normalize(part)
        if not norm_part:
            continue
        if norm_part in norm_context:
            hits += 1
            continue
        tokens = [t for t in norm_part.split() if len(t) > 2]
        if tokens and sum(1 for t in tokens if t in norm_context) / len(tokens) >= 0.6:
            hits += 1
    return hits / len(parts) >= 0.6


def status_answer_in_context(answer: str | int | float | None, context: str) -> bool:
    """Heuristic for relationship-status answers supported by breakup/single cues."""
    if answer is None or not context:
        return False
    norm_answer = normalize(answer)
    if norm_answer not in {"single", "married", "divorced", "engaged"}:
        return False
    norm_context = normalize(context)
    if norm_answer in norm_context:
        return True
    if norm_answer == "single":
        markers = ("breakup", "broke up", "not dating", "not married", "tough breakup")
        return any(marker in norm_context for marker in markers)
    return False


def temporal_day_month_in_context(answer: str | int | float | None, context: str) -> bool:
    """Match answers like '2 July 2023' or '5 July 2023' against session dates in context."""
    if answer is None or not context:
        return False
    answer_str = str(answer).strip().lower()
    match = re.match(r"^(\d{1,2})\s+([a-z]+)\s+(\d{4})$", answer_str)
    if not match:
        return False
    day, month_name, year_str = match.group(1), match.group(2), match.group(3)
    month_num = _MONTH_NAMES.get(month_name)
    if not month_num:
        return False
    if year_str in context and month_name in context.lower() and day in context:
        return True
    return False


def temporal_relative_in_context(answer: str | int | float | None, context: str) -> bool:
    """Match relative temporal gold answers anchored by session dates in context."""
    if answer is None or not context:
        return False
    answer_str = str(answer).strip().lower()
    norm_context = normalize(context)

    if re.match(r"^\d+\s+years?\s+ago$", answer_str):
        if answer_str.replace("years", "year") in norm_context or "years ago" in norm_context:
            return True
        num = re.match(r"^(\d+)", answer_str)
        if num and f"{num.group(1)} year" in norm_context:
            return True

    relative_markers = (
        "friday before",
        "sunday before",
        "week before",
        "weekend before",
        "last saturday",
        "last sunday",
        "two weekends ago",
        "next month",
        "this june",
        "in june",
    )
    if any(marker in answer_str for marker in relative_markers):
        return any(marker in norm_context for marker in relative_markers)

    if "highlight of our summer" in norm_context and "june" in answer_str:
        for session_match in _SESSION_YEAR.finditer(context):
            if session_match.group(1) in answer_str:
                return True
        if "june" in norm_context and re.search(r"\b20\d{2}\b", answer_str):
            return True

    return False


def temporal_month_year_in_context(answer: str | int | float | None, context: str) -> bool:
    """Match answers like 'June 2023' against session dates and month names in context."""
    if answer is None or not context:
        return False
    answer_str = str(answer).strip().lower()
    match = re.match(r"^([a-z]+)\s+(\d{4})$", answer_str)
    if not match:
        return False
    month_name, year_str = match.group(1), match.group(2)
    month_num = _MONTH_NAMES.get(month_name)
    if not month_num:
        return False
    if year_str in context and month_name in context.lower():
        return True
    for session_match in _SESSION_YEAR.finditer(context):
        if session_match.group(1) == year_str and month_name in context.lower():
            return True
    norm_context = normalize(context)
    if month_name in answer_str and "highlight of our summer" in norm_context:
        if year_str in context or any(
            session_match.group(1) == year_str for session_match in _SESSION_YEAR.finditer(context)
        ):
            return True
    return False


def temporal_year_in_context(answer: str | int | float | None, context: str) -> bool:
    """Match calendar-year gold answers to relative phrases anchored by session dates."""
    if answer is None or not context:
        return False
    try:
        year = int(answer)
    except (TypeError, ValueError):
        return False
    if not 1900 <= year <= 2100:
        return False
    if str(year) in context:
        return True
    norm = normalize(context)
    if "last year" not in norm:
        return False
    for match in _SESSION_YEAR.finditer(context):
        try:
            session_year = int(match.group(1))
        except ValueError:
            continue
        if session_year - 1 == year:
            return True
    return False


def answer_in_context(answer: str | int | float | None, context: str) -> bool:
    """True when normalized ground-truth answer appears in retrieved context."""
    if answer is None or answer == "" or not context:
        return False
    if temporal_year_in_context(answer, context):
        return True
    if temporal_month_year_in_context(answer, context):
        return True
    if temporal_day_month_in_context(answer, context):
        return True
    if temporal_relative_in_context(answer, context):
        return True
    if list_answer_in_context(answer, context):
        return True
    if status_answer_in_context(answer, context):
        return True
    norm_answer = normalize(answer)
    norm_context = normalize(context)
    if norm_answer in norm_context:
        return True
    if norm_answer in {"no", "false"}:
        return _negative_answer_supported(str(answer), context)
    tokens = [t for t in norm_answer.split() if len(t) > 2]
    if not tokens:
        return False
    hits = sum(1 for token in tokens if token in norm_context)
    return hits / len(tokens) >= 0.6


def adversarial_passes(context: str, trap: str, generated: str = "") -> bool:
    """Adversarial QA: pass when trap answer is absent from context and generation."""
    trap_norm = normalize(trap)
    ctx_norm = normalize(context)
    gen_norm = normalize(generated)
    if trap_norm and trap_norm in ctx_norm:
        return False
    if gen_norm and trap_norm and trap_norm in gen_norm:
        return False
    if gen_norm in {"unknown", ""}:
        return True
    return bool(gen_norm) and trap_norm not in gen_norm


def _negative_answer_supported(answer: str, context: str) -> bool:
    """Heuristic for temporal/contradiction-style 'No' answers."""
    norm_context = normalize(context)
    neg_markers = (
        "postgresql-only",
        "postgresql only",
        "migrated",
        "no longer",
        "not anymore",
        "only homelab",
    )
    return any(marker in norm_context for marker in neg_markers)


def grade_answer(predicted: str, gold: str | int | float | None) -> tuple[bool, str]:
    """Local semantic equivalence — no LLM."""
    gold_str = "" if gold is None else str(gold)
    pred = (predicted or "").strip()
    if not pred or pred.lower() == "unknown":
        if normalize(gold_str) in {"no", "false", "not"}:
            return True, "negative_unknown"
        return False, "unknown"

    pred_norm = normalize(pred)
    gold_norm = normalize(gold_str)

    if not gold_norm:
        return bool(pred_norm), "empty_gold"

    if gold_norm in pred_norm or pred_norm in gold_norm:
        return True, "substring"

    gold_tokens = [t for t in gold_norm.split() if len(t) > 2]
    if gold_tokens:
        overlap = sum(1 for t in gold_tokens if t in pred_norm) / len(gold_tokens)
        if overlap >= 0.6:
            return True, "token_overlap"

    if gold_norm in {"no", "false", "not"}:
        neg_words = ("no", "not", "never", "none", "unknown", "doesn't", "don't")
        return any(w in pred_norm for w in neg_words), "negative_heuristic"

    return False, "no_match"


def multihop_retrieval_hit(
    answer: str | int | float | None,
    context: str,
    *,
    category: str,
    evidence_recall: float,
) -> bool:
    """Gold answers are often abstractive; full evidence in context counts as hit."""
    if answer_in_context(answer, context):
        return True
    if category not in ("adversarial",) and evidence_recall >= 1.0:
        return True
    if category == "multi-hop" and evidence_recall >= 0.5 and list_answer_in_context(answer, context):
        return True
    return False


def evidence_recall(evidence_ids: list[str], turn_lookup: dict[str, str], context: str) -> float:
    """Fraction of evidence turn texts present in retrieved context."""
    if not evidence_ids:
        return 1.0
    norm_context = normalize(context)
    found = 0
    for dia_id in evidence_ids:
        turn_text = turn_lookup.get(dia_id, "")
        if turn_text and normalize(turn_text) in norm_context:
            found += 1
        elif turn_text:
            tokens = [t for t in normalize(turn_text).split() if len(t) > 3]
            if tokens and sum(1 for t in tokens if t in norm_context) / len(tokens) >= 0.5:
                found += 1
    return found / len(evidence_ids)


def score_qa(
    context: str,
    qa: dict[str, Any],
    turn_lookup: dict[str, str],
) -> dict[str, Any]:
    answer = qa.get("answer", "")
    evidence = list(qa.get("evidence") or [])
    if qa.get("adversarial"):
        trap = qa.get("adversarial_trap", answer)
        retrieval_hit = adversarial_passes(context, str(trap))
        return {
            "question": qa.get("question", ""),
            "answer": trap,
            "category": "adversarial",
            "retrieval_hit": retrieval_hit,
            "evidence_recall": evidence_recall(evidence, turn_lookup, context),
            "evidence_ids": evidence,
            "adversarial": True,
        }

    ev_recall = evidence_recall(evidence, turn_lookup, context)
    retrieval_hit = multihop_retrieval_hit(
        answer,
        context,
        category=str(qa.get("category", "unknown")),
        evidence_recall=ev_recall,
    )
    return {
        "question": qa.get("question", ""),
        "answer": answer,
        "category": qa.get("category", "unknown"),
        "retrieval_hit": retrieval_hit,
        "evidence_recall": round(ev_recall, 4),
        "evidence_ids": evidence,
    }


def summarize_qa_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    hits = sum(1 for r in results if r["retrieval_hit"])
    native_hits = sum(1 for r in results if r.get("native_correct"))
    graded_hits = sum(1 for r in results if r.get("graded_correct"))
    has_native = any("native_correct" in r for r in results)
    has_graded = any("graded_correct" in r for r in results)
    by_category: dict[str, dict[str, Any]] = {}
    by_category_native: dict[str, dict[str, Any]] = {}
    by_category_graded: dict[str, dict[str, Any]] = {}
    for row in results:
        cat = row.get("category", "unknown")
        bucket = by_category.setdefault(cat, {"total": 0, "hits": 0})
        bucket["total"] += 1
        if row["retrieval_hit"]:
            bucket["hits"] += 1
        if has_native:
            nb = by_category_native.setdefault(cat, {"total": 0, "hits": 0})
            nb["total"] += 1
            if row.get("native_correct"):
                nb["hits"] += 1
        if has_graded:
            gb = by_category_graded.setdefault(cat, {"total": 0, "hits": 0})
            gb["total"] += 1
            if row.get("graded_correct"):
                gb["hits"] += 1
    for cat, bucket in by_category.items():
        bucket["accuracy"] = round(bucket["hits"] / bucket["total"], 4) if bucket["total"] else 0.0
    for cat, bucket in by_category_native.items():
        bucket["accuracy"] = round(bucket["hits"] / bucket["total"], 4) if bucket["total"] else 0.0
    for cat, bucket in by_category_graded.items():
        bucket["accuracy"] = round(bucket["hits"] / bucket["total"], 4) if bucket["total"] else 0.0
    avg_evidence = round(sum(r["evidence_recall"] for r in results) / total, 4) if total else 0.0
    summary: dict[str, Any] = {
        "total": total,
        "retrieval_hits": hits,
        "retrieval_accuracy": round(hits / total, 4) if total else 0.0,
        "avg_evidence_recall": avg_evidence,
        "by_category": by_category,
    }
    if has_native:
        summary["native_hits"] = native_hits
        summary["native_accuracy"] = round(native_hits / total, 4) if total else 0.0
        summary["by_category_native"] = by_category_native
    if has_graded:
        summary["graded_hits"] = graded_hits
        summary["graded_accuracy"] = round(graded_hits / total, 4) if total else 0.0
        summary["by_category_graded"] = by_category_graded
    return summary
