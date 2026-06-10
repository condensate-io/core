"""Assertion supersession — temporal validity and canonical state chains."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import Assertion


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _subject_key(assertion: Assertion) -> Tuple[Optional[uuid.UUID], str, str]:
    return (
        assertion.subject_entity_id,
        (assertion.subject_text or "").strip().lower(),
        (assertion.predicate or "").strip().lower(),
    )


def find_conflicting_assertions(
    db: Session,
    project_id: uuid.UUID,
    *,
    subject_entity_id: Optional[uuid.UUID],
    subject_text: Optional[str],
    predicate: str,
    object_text: Optional[str],
    object_entity_id: Optional[uuid.UUID],
) -> List[Assertion]:
    """Find active assertions for the same subject+predicate with a different object."""
    subj_text_norm = (subject_text or "").strip().lower()
    pred_norm = (predicate or "").strip().lower()
    obj_text_norm = (object_text or "").strip().lower()

    stmt = select(Assertion).where(
        Assertion.project_id == project_id,
        Assertion.status.in_(["approved", "active", "pending_review"]),
        Assertion.predicate == pred_norm,
    )
    if subject_entity_id:
        stmt = stmt.where(Assertion.subject_entity_id == subject_entity_id)
    else:
        stmt = stmt.where(Assertion.subject_text == subject_text)

    candidates = db.execute(stmt).scalars().all()
    conflicts: List[Assertion] = []
    for row in candidates:
        same_object = False
        if object_entity_id and row.object_entity_id:
            same_object = row.object_entity_id == object_entity_id
        elif obj_text_norm and row.object_text:
            same_object = row.object_text.strip().lower() == obj_text_norm
        if not same_object:
            conflicts.append(row)
    return conflicts


def apply_supersession(
    db: Session,
    new_assertion: Assertion,
    *,
    valid_from: Optional[datetime] = None,
) -> None:
    """Mark prior conflicting assertions as superseded by the new one."""
    now = valid_from or _now()
    conflicts = find_conflicting_assertions(
        db,
        new_assertion.project_id,
        subject_entity_id=new_assertion.subject_entity_id,
        subject_text=new_assertion.subject_text,
        predicate=new_assertion.predicate,
        object_text=new_assertion.object_text,
        object_entity_id=new_assertion.object_entity_id,
    )
    for old in conflicts:
        if old.id == new_assertion.id:
            continue
        old.valid_until = now
        old.status = "superseded"
        db.add(old)

    new_assertion.valid_from = new_assertion.valid_from or now
    new_assertion.valid_until = None
    if conflicts:
        new_assertion.supersedes_id = conflicts[0].id
    prov = new_assertion.provenance or []
    new_assertion.evidence_count = len(prov)


def fetch_supersession_chain(db: Session, assertion_id: uuid.UUID) -> List[Assertion]:
    """Walk backward through supersedes_id links (oldest first)."""
    chain: List[Assertion] = []
    current_id: Optional[uuid.UUID] = assertion_id
    seen: set[uuid.UUID] = set()
    while current_id and current_id not in seen:
        seen.add(current_id)
        row = db.get(Assertion, current_id)
        if not row:
            break
        chain.append(row)
        current_id = row.supersedes_id
    chain.reverse()
    return chain


def latest_valid_assertions(
    db: Session,
    project_id: uuid.UUID,
    *,
    subject_text: Optional[str] = None,
    predicate: Optional[str] = None,
    limit: int = 25,
) -> List[Assertion]:
    """Return currently valid (non-superseded) assertions ordered by recency."""
    stmt = select(Assertion).where(
        Assertion.project_id == project_id,
        Assertion.status.in_(["approved", "active"]),
        Assertion.valid_until.is_(None),
    )
    if subject_text:
        pattern = f"%{subject_text}%"
        stmt = stmt.where(Assertion.subject_text.ilike(pattern))
    if predicate:
        stmt = stmt.where(Assertion.predicate.ilike(f"%{predicate}%"))
    return (
        db.execute(
            stmt.order_by(
                Assertion.confidence.desc(),
                Assertion.strength.desc(),
                Assertion.last_seen_at.desc(),
            ).limit(limit)
        )
        .scalars()
        .all()
    )
