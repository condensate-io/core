import uuid
import hashlib
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from src.db.models import IngestJob, IngestJobRun, FetchedArtifact
from src.ingest.connectors.web import WebURLConnector
import threading
from src.engine.scheduler import _log_job

# Registry of available connectors
CONNECTORS = {
    "web": WebURLConnector(),
    # "chroma": ChromaConnector(),
    # "push": PushConnector(),
}

class IngestService:
    def __init__(self, db: Session):
        self.db = db

    def create_job(self, project_id: uuid.UUID, source_type: str, source_config: dict, trigger_type: str, trigger_config: dict) -> IngestJob:
        job = IngestJob(
            project_id=project_id,
            source_type=source_type,
            source_config=source_config,
            trigger_type=trigger_type,
            trigger_config=trigger_config
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def run_job(self, job_id: uuid.UUID) -> IngestJobRun:
        job = self.db.query(IngestJob).filter(IngestJob.id == job_id).first()
        if not job:
            raise ValueError("Job not found")

        run = IngestJobRun(
            job_id=job.id,
            status="running",
            started_at=datetime.utcnow()
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        # Log to in-memory job log for UI
        _log_job(str(run.id), f"Ingest: {job.source_type}", "running", run.started_at)

        try:
            connector = CONNECTORS.get(job.source_type)
            if not connector:
                raise ValueError(f"No connector for type {job.source_type}")

            items = connector.discover(job.source_config)
            
            stats = {"fetched": 0, "bytes": 0}
            
            for item_ref in items:
                for uri, content, meta in connector.fetch(job.source_config, item_ref):
                    # Deduping hash
                    content_hash = hashlib.sha256(content).hexdigest()
                    
                    # Store Raw Artifact
                    artifact = FetchedArtifact(
                        run_id=run.id,
                        job_id=job.id,
                        source_uri=uri,
                        content_hash=content_hash,
                        content=content.decode('utf-8', errors='ignore'), # Assuming text for now
                        metadata_=meta
                    )
                    self.db.add(artifact)
                    stats["fetched"] += 1
                    stats["bytes"] += len(content)




            run.status = "completed"
            run.ended_at = datetime.utcnow()
            run.stats = stats
            self.db.commit()
            
            _log_job(str(run.id), f"Ingest: {job.source_type}", "success", run.started_at, run.ended_at)
            
            # Trigger Condensation Pipeline
            try:
                # Run condensation in a background thread to unblock the ingestion job
                
                # We need to capture the necessary IDs and data to pass to the thread
                # The thread must manage its own DB session
                job_id = job.id
                project_id = job.project_id
                run_id = run.id
                source_type = job.source_type
                
                thread = threading.Thread(
                    target=self._run_condensation_task,
                    args=(job_id, project_id, run_id, source_type)
                )
                thread.start()

            except Exception as e:
                print(f"Warning: Failed to trigger condensation: {e}")
            
            return run

        except Exception as e:
            run.status = "failed"
            run.ended_at = datetime.utcnow()
            run.error_log = str(e)
            self.db.commit()
            _log_job(str(run.id), f"Ingest: {job.source_type}", "error", run.started_at, datetime.utcnow(), error=str(e))
            raise e

    def _run_condensation_task(self, job_id: uuid.UUID, project_id: uuid.UUID, run_id: uuid.UUID, source_type: str):
        """
        Background task for condensation.
        Must use its own DB session.
        """
        import asyncio
        import os
        from src.agents.ingress import IngressAgent
        from src.db.schemas import EpisodicItemCreate
        from qdrant_client import QdrantClient
        from src.db.session import SessionLocal
        
        print(f"Starting background condensation for run {run_id}")
        
        start_time = datetime.utcnow()
        _log_job(f"condense_{run_id}", f"Condense: {run_id}", "running", start_time)
        
        # New DB Session for this thread
        db = SessionLocal()
        
        try:
            # Fetch all newly created artifacts
            # We must re-query them in this new session
            new_artifacts = db.query(FetchedArtifact).filter(
                FetchedArtifact.run_id == run_id
            ).all()

            async def process_ingested_artifacts_async():
                # Initialize IngressAgent (loads embedding model)
                qdrant = QdrantClient(
                    host=os.getenv("QDRANT_HOST", "localhost"),
                    port=int(os.getenv("QDRANT_PORT", 6333))
                )
                ingress = IngressAgent(db, qdrant)
                
                # Transform all artifacts to EpisodicItemCreate batch
                items_to_process = [
                    EpisodicItemCreate(
                        project_id=str(project_id),
                        text=artifact.content,
                        source=source_type,
                        metadata={"artifact_id": str(artifact.id), "source_uri": artifact.source_uri}
                    )
                    for artifact in new_artifacts
                ]
                
                if items_to_process:
                    # Process and condense in a single batch call
                    await ingress.process_and_condense_batch(items_to_process)

            # Run async condensation in this thread
            asyncio.run(process_ingested_artifacts_async())

            print(f"Condensed {len(new_artifacts)} artifacts for run {run_id}.")
            _log_job(f"condense_{run_id}", f"Condense: {run_id}", "success", start_time, datetime.utcnow())

        except Exception as e:
            print(f"Error in background condensation for run {run_id}: {e}")
            _log_job(f"condense_{run_id}", f"Condense: {run_id}", "error", start_time, datetime.utcnow(), error=str(e))
        finally:
            db.close()
