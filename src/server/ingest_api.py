from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.ingest.service import IngestService
from src.db.models import IngestJob, IngestJobRun
from pydantic import BaseModel
import uuid
from typing import Dict, Any

router = APIRouter(prefix="/v1/ingest", tags=["ingest"])

class IngestJobCreate(BaseModel):
    project_id: uuid.UUID
    source_type: str
    source_config: Dict[str, Any]
    trigger_type: str = "on_demand"
    trigger_config: Dict[str, Any] = {}

class IngestJobResponse(BaseModel):
    id: uuid.UUID
    state: str
    
@router.post("/jobs", response_model=IngestJobResponse)
def create_job(job: IngestJobCreate, db: Session = Depends(get_db)):
    service = IngestService(db)
    new_job = service.create_job(
        project_id=job.project_id,
        source_type=job.source_type,
        source_config=job.source_config,
        trigger_type=job.trigger_type,
        trigger_config=job.trigger_config
    )
    return IngestJobResponse(id=new_job.id, state=new_job.state)

@router.post("/jobs/{job_id}/run")
def trigger_job_run(job_id: uuid.UUID, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    service = IngestService(db)
    # Validate job exists
    job = db.query(IngestJob).filter(IngestJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Run in background
    background_tasks.add_task(run_ingest_job_background, job_id)
    
    return {"status": "queued", "job_id": str(job_id)}

def run_ingest_job_background(job_id: uuid.UUID):
    from src.db.session import SessionLocal
    from src.ingest.service import IngestService
    import logging
    
    logger = logging.getLogger("IngestBackground")
    db = SessionLocal()
    try:
        service = IngestService(db)
        service.run_job(job_id)
    except Exception as e:
        logger.error(f"Background ingest job {job_id} failed: {e}")
    finally:
        db.close()
