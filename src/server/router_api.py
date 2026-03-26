from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Union
import logging
from src.db.session import get_db, get_qdrant
from sqlalchemy.orm import Session
from qdrant_client import QdrantClient
from src.retrieve.router import MemoryRouter

router = APIRouter(prefix="/memory", tags=["Memory Router"])
logger = logging.getLogger(__name__)

class RetrieveRequest(BaseModel):
    project_id: Any # str or List[str]
    query: str

class RetrieveResponse(BaseModel):
    answer: str
    sources: List[str]
    strategy: str

@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_memory(
    request: RetrieveRequest,
    db: Session = Depends(get_db),
    qdrant: QdrantClient = Depends(get_qdrant)
):
    try:
        mr = MemoryRouter(db, qdrant)
        result = await mr.route_and_retrieve(request.project_id, request.query)
        return RetrieveResponse(**result)
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
