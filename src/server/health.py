import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from qdrant_client import QdrantClient
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.db.session import get_db, get_qdrant

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


def _check_postgres(db: Session) -> str:
    db.execute(text("SELECT 1"))
    return "ok"


def _check_qdrant(qdrant: QdrantClient) -> str:
    qdrant.get_collections()
    return "ok"


@router.get("/healthz")
@router.get("/health")
def healthz(
    db: Session = Depends(get_db),
    qdrant: QdrantClient = Depends(get_qdrant),
) -> JSONResponse:
    checks: Dict[str, Any] = {}
    healthy = True

    try:
        checks["postgres"] = _check_postgres(db)
    except Exception as exc:
        logger.warning("Postgres health check failed: %s", exc)
        checks["postgres"] = str(exc)
        healthy = False

    try:
        checks["qdrant"] = _check_qdrant(qdrant)
    except Exception as exc:
        logger.warning("Qdrant health check failed: %s", exc)
        checks["qdrant"] = str(exc)
        healthy = False

    payload = {"status": "ok" if healthy else "degraded", "checks": checks}
    return JSONResponse(status_code=200 if healthy else 503, content=payload)
