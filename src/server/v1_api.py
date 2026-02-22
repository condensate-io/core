from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional
from src.db.session import get_db
from src.db.models import EpisodicItem, Entity, Assertion

router = APIRouter(prefix="/v1", tags=["v1"])

# --- Episodic API ---

@router.get("/episodic")
def get_episodic_items(
    project_id: Optional[str] = None, 
    source: Optional[str] = None,
    limit: int = 100, 
    offset: int = 0,
    db: Session = Depends(get_db)
):
    stmt = select(EpisodicItem)
    if project_id:
        stmt = stmt.where(EpisodicItem.project_id == project_id)
    if source:
        stmt = stmt.where(EpisodicItem.source == source)
    
    stmt = stmt.order_by(EpisodicItem.occurred_at.desc()).limit(limit).offset(offset)
    items = db.execute(stmt).scalars().all()
    
    return [
        {
            "id": str(i.id),
            "project_id": str(i.project_id),
            "source": i.source,
            "text": i.text,
            "occurred_at": i.occurred_at,
            "metadata": i.metadata_
        }
        for i in items
    ]

# --- Graph API ---

@router.get("/graph/entities")
def get_entities(
    project_id: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    stmt = select(Entity)
    if project_id:
        stmt = stmt.where(Entity.project_id == project_id)
    if type:
        stmt = stmt.where(Entity.type == type)
        
    stmt = stmt.limit(limit)
    entities = db.execute(stmt).scalars().all()
    
    return [
        {
            "id": str(e.id),
            "name": e.canonical_name,
            "type": e.type,
            "aliases": e.aliases,
            "confidence": e.confidence
        }
        for e in entities
    ]

@router.get("/graph/assertions")
def get_assertions(
    project_id: Optional[str] = None,
    subject: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    stmt = select(Assertion)
    if project_id:
        stmt = stmt.where(Assertion.project_id == project_id)
    if subject:
        # Simple text match for MVP
        stmt = stmt.where(Assertion.subject_text.ilike(f"%{subject}%"))
        
    stmt = stmt.limit(limit)
    assertions = db.execute(stmt).scalars().all()
    
    return [
        {
            "id": str(a.id),
            "subject": a.subject_text,
            "predicate": a.predicate,
            "object": a.object_text,
            "confidence": a.confidence,
            "status": a.status,
            "provenance": a.provenance
        }
        for a in assertions
    ]

# --- Export API ---

@router.get("/export/jsonl")
def export_jsonl(project_id: str, db: Session = Depends(get_db)):
    # Streaming response would be better for large datasets, 
    # but for MVP returning a line-delimited string or list
    
    # 1. Fetch all items
    items = db.execute(select(EpisodicItem).where(EpisodicItem.project_id == project_id)).scalars().all()
    
    # 2. Fetch all assertions
    assertions = db.execute(select(Assertion).where(Assertion.project_id == project_id)).scalars().all()
    
    import json
    lines = []
    
    for i in items:
        lines.append(json.dumps({
            "type": "episodic_item",
            "id": str(i.id),
            "text": i.text,
            "source": i.source,
            "created_at": i.created_at.isoformat()
        }))
        
    for a in assertions:
        lines.append(json.dumps({
            "type": "assertion",
            "id": str(a.id),
            "statement": f"{a.subject_text} {a.predicate} {a.object_text}",
            "confidence": a.confidence,
            "provenance": a.provenance
        }))
        
    from fastapi.responses import Response
    return Response(content="\n".join(lines), media_type="application/x-jsonlines")
