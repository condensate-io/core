import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from sqlalchemy.orm import Session

from src.db.models import ApiKey
from src.db.session import get_db, get_qdrant
from src.engine.feedback import MemoryFeedbackService
from src.retrieve.router import MemoryRouter
from src.server.admin import get_api_key

router = APIRouter(prefix="/memory", tags=["Memory Router"])
logger = logging.getLogger(__name__)


class RetrieveRequest(BaseModel):
    project_id: Optional[Any] = None  # Optional now since it's forced by API key
    query: str
    session_id: Optional[str] = None


class RetrieveResponse(BaseModel):
    answer: str
    context: str = ""
    sources: List[str]
    strategy: str
    question_type: str = "exact_fact"
    recall_plan: Dict[str, Any] = Field(default_factory=dict)
    verification: Dict[str, Any] = Field(default_factory=dict)


class MemoryFeedbackRequest(BaseModel):
    source_ids: List[str]
    correct: bool
    gold_evidence_ids: List[str] = Field(default_factory=list)
    retrieval_path: List[str] = Field(default_factory=list)


class MemoryFeedbackResponse(BaseModel):
    strengthened: int = 0
    decayed: int = 0
    path: List[str] = Field(default_factory=list)


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_memory(
    request: RetrieveRequest,
    db: Session = Depends(get_db),
    qdrant: QdrantClient = Depends(get_qdrant),
    api_key: ApiKey = Depends(get_api_key),
):
    try:
        # Benchmark harness sends per-conversation project_id; otherwise scope to API key.
        if request.project_id is not None:
            project_id = str(request.project_id)
        else:
            project_id = str(api_key.project_id)
        mr = MemoryRouter(db, qdrant)
        result = await mr.route_and_retrieve(
            project_id,
            request.query,
            session_id=request.session_id,
        )
        payload = {
            k: result[k]
            for k in (
                "answer",
                "context",
                "sources",
                "strategy",
                "question_type",
                "recall_plan",
                "verification",
            )
            if k in result
        }
        return RetrieveResponse(**payload)
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback", response_model=MemoryFeedbackResponse)
async def memory_feedback(
    request: MemoryFeedbackRequest,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key),
):
    del api_key
    import uuid

    try:
        source_ids = [uuid.UUID(s) for s in request.source_ids]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid source_id: {exc}") from exc

    service = MemoryFeedbackService(db)
    outcome = service.apply_feedback(
        source_ids,
        correct=request.correct,
        gold_evidence_ids=request.gold_evidence_ids,
        retrieval_path=request.retrieval_path,
    )
    return MemoryFeedbackResponse(**outcome)
