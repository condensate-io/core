from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from src.db.session import get_db
from src.db.models import Assertion
from pydantic import BaseModel

router = APIRouter(prefix="/api/admin/review", tags=["review"])


class ApprovalRequest(BaseModel):
    reviewed_by: str = "admin"


class RejectionRequest(BaseModel):
    reviewed_by: str = "admin"
    rejection_reason: str


class BulkApprovalRequest(BaseModel):
    assertion_ids: List[str]
    reviewed_by: str = "admin"


@router.get("/assertions/pending")
def list_pending_assertions(
    limit: int = 50,
    offset: int = 0,
    min_instruction_score: Optional[float] = None,
    min_safety_score: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """
    List all pending assertions awaiting review.
    Optionally filter by guardrail scores.
    """
    query = select(Assertion).where(Assertion.status == "pending_review")
    
    if min_instruction_score is not None:
        query = query.where(Assertion.instruction_score >= min_instruction_score)
    
    if min_safety_score is not None:
        query = query.where(Assertion.safety_score >= min_safety_score)
    
    query = query.order_by(Assertion.first_seen_at.desc()).limit(limit).offset(offset)
    
    assertions = db.execute(query).scalars().all()
    
    return {
        "total": len(assertions),
        "assertions": [
            {
                "id": str(a.id),
                "subject_text": a.subject_text,
                "predicate": a.predicate,
                "object_text": a.object_text,
                "confidence": a.confidence,
                "instruction_score": a.instruction_score,
                "safety_score": a.safety_score,
                "first_seen_at": a.first_seen_at.isoformat() if a.first_seen_at else None,
                "provenance": a.provenance
            }
            for a in assertions
        ]
    }


@router.post("/assertions/{assertion_id}/approve")
def approve_assertion(
    assertion_id: str,
    request: ApprovalRequest,
    db: Session = Depends(get_db)
):
    """
    Approve a pending assertion, making it active in the knowledge graph.
    """
    try:
        aid = uuid.UUID(assertion_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid assertion ID")
    
    assertion = db.query(Assertion).filter(Assertion.id == aid).first()
    
    if not assertion:
        raise HTTPException(status_code=404, detail="Assertion not found")
    
    if assertion.status != "pending_review":
        raise HTTPException(status_code=400, detail=f"Assertion is not pending review (status: {assertion.status})")
    
    # Update status
    assertion.status = "approved"
    assertion.reviewed_by = request.reviewed_by
    assertion.reviewed_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "status": "approved",
        "id": assertion_id,
        "reviewed_by": request.reviewed_by,
        "reviewed_at": assertion.reviewed_at.isoformat()
    }


@router.post("/assertions/{assertion_id}/reject")
def reject_assertion(
    assertion_id: str,
    request: RejectionRequest,
    db: Session = Depends(get_db)
):
    """
    Reject a pending assertion with a reason.
    """
    try:
        aid = uuid.UUID(assertion_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid assertion ID")
    
    assertion = db.query(Assertion).filter(Assertion.id == aid).first()
    
    if not assertion:
        raise HTTPException(status_code=404, detail="Assertion not found")
    
    if assertion.status != "pending_review":
        raise HTTPException(status_code=400, detail=f"Assertion is not pending review (status: {assertion.status})")
    
    # Update status
    assertion.status = "rejected"
    assertion.reviewed_by = request.reviewed_by
    assertion.reviewed_at = datetime.utcnow()
    assertion.rejection_reason = request.rejection_reason
    
    db.commit()
    
    return {
        "status": "rejected",
        "id": assertion_id,
        "reviewed_by": request.reviewed_by,
        "reviewed_at": assertion.reviewed_at.isoformat(),
        "rejection_reason": request.rejection_reason
    }


@router.post("/assertions/bulk-approve")
def bulk_approve_assertions(
    request: BulkApprovalRequest,
    db: Session = Depends(get_db)
):
    """
    Approve multiple assertions in a single request.
    """
    approved_count = 0
    errors = []
    
    for assertion_id_str in request.assertion_ids:
        try:
            aid = uuid.UUID(assertion_id_str)
            assertion = db.query(Assertion).filter(Assertion.id == aid).first()
            
            if not assertion:
                errors.append(f"{assertion_id_str}: not found")
                continue
            
            if assertion.status != "pending_review":
                errors.append(f"{assertion_id_str}: not pending review")
                continue
            
            assertion.status = "approved"
            assertion.reviewed_by = request.reviewed_by
            assertion.reviewed_at = datetime.utcnow()
            approved_count += 1
            
        except ValueError:
            errors.append(f"{assertion_id_str}: invalid ID")
    
    db.commit()
    
    return {
        "approved_count": approved_count,
        "total_requested": len(request.assertion_ids),
        "errors": errors
    }
