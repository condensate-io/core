import uuid
import hashlib
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.db.models import IngestJob, IngestJobRun, FetchedArtifact
from src.ingest.connectors.web import WebURLConnector
from src.ingest.connectors.codebase import CodebaseConnector
from src.engine.job_history import log_job as _log_job
from src.engine.thread_shard import get_thread_shard

# Registry of available connectors
CONNECTORS = {
    "web": WebURLConnector(),
    "codebase": CodebaseConnector(),
    # "chroma": ChromaConnector(),
    # "push": PushConnector(),
}

logger = logging.getLogger(__name__)

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

    def _load_existing_hashes(self, job_id: uuid.UUID) -> Dict[str, str]:
        """
        Preload the most recent content_hash per source_uri for this job in a
        single query, so unchanged files can be skipped on repeat ingests
        without re-condensing them (one query instead of one-per-file).
        """
        rows = self.db.execute(
            select(
                FetchedArtifact.source_uri,
                FetchedArtifact.content_hash,
                FetchedArtifact.created_at,
            ).where(FetchedArtifact.job_id == job_id)
        ).all()

        latest: Dict[str, Tuple[str, datetime]] = {}
        for source_uri, content_hash, created_at in rows:
            prev = latest.get(source_uri)
            if prev is None or (created_at and prev[1] and created_at > prev[1]):
                latest[source_uri] = (content_hash, created_at)

        return {uri: h for uri, (h, _) in latest.items()}

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

        stage_timings: Dict[str, int] = {}

        try:
            connector = CONNECTORS.get(job.source_type)
            if not connector:
                raise ValueError(f"No connector for type {job.source_type}")

            t0 = time.monotonic()
            items = connector.discover(job.source_config)
            stage_timings["discover_ms"] = int((time.monotonic() - t0) * 1000)

            stats = {"fetched": 0, "bytes": 0, "skipped_unchanged": 0}

            existing_hashes = self._load_existing_hashes(job.id)

            # Fetching (reading files/URLs) is I/O-bound, so parallelize it
            # across the shared adaptive thread pool. DB writes stay on the
            # calling thread/session, which is not safe to share across
            # threads.
            t0 = time.monotonic()
            shard = get_thread_shard()

            def _fetch_one(ref):
                return list(connector.fetch(job.source_config, ref))

            fetch_futures = [shard.submit(_fetch_one, item_ref) for item_ref in items]

            for future in fetch_futures:
                try:
                    results = future.result()
                except Exception as e:
                    logger.warning("Failed to fetch item: %s", e)
                    continue

                for uri, content, meta in results:
                    # Deduping hash
                    content_hash = hashlib.sha256(content).hexdigest()

                    # Skip artifacts whose content is unchanged since the
                    # last run of this job, avoiding redundant storage and
                    # (much more expensive) re-condensation of identical text.
                    if existing_hashes.get(uri) == content_hash:
                        stats["skipped_unchanged"] += 1
                        continue

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
                    existing_hashes[uri] = content_hash
                    stats["fetched"] += 1
                    stats["bytes"] += len(content)

            stage_timings["fetch_ms"] = int((time.monotonic() - t0) * 1000)

            run.status = "completed"
            run.ended_at = datetime.utcnow()
            run.stats = stats
            self.db.commit()

            _log_job(
                str(run.id), f"Ingest: {job.source_type}", "success",
                run.started_at, run.ended_at,
                duration_ms=int((run.ended_at - run.started_at).total_seconds() * 1000),
                stages=stage_timings,
            )

            # Trigger Condensation Pipeline
            try:
                # Run condensation on the shared adaptive thread pool (instead
                # of an unbounded bare threading.Thread per run) to unblock
                # the ingestion request while still bounding total concurrency.
                job_id = job.id
                project_id = job.project_id
                run_id = run.id
                source_type = job.source_type

                get_thread_shard().submit(
                    self._run_condensation_task,
                    job_id, project_id, run_id, source_type,
                )

            except Exception as e:
                logger.warning("Failed to trigger condensation: %s", e)

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
        
        logger.info("Starting background condensation for run %s", run_id)
        
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
                        metadata={
                            "artifact_id": str(artifact.id),
                            "source_uri": artifact.source_uri,
                            **(artifact.metadata_ or {}),
                        },
                    )
                    for artifact in new_artifacts
                ]
                
                if items_to_process:
                    # Process and condense in a single batch call
                    await ingress.process_and_condense_batch(items_to_process)

            # Run async condensation in this thread
            asyncio.run(process_ingested_artifacts_async())

            logger.info("Condensed %s artifacts for run %s.", len(new_artifacts), run_id)
            _log_job(f"condense_{run_id}", f"Condense: {run_id}", "success", start_time, datetime.utcnow())

        except Exception as e:
            logger.error("Error in background condensation for run %s: %s", run_id, e)
            _log_job(f"condense_{run_id}", f"Condense: {run_id}", "error", start_time, datetime.utcnow(), error=str(e))
        finally:
            db.close()
