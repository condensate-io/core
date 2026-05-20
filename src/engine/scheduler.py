from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from qdrant_client import QdrantClient
import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any

from src.db.session import SessionLocal
from src.db.models import DataSource, Project
from src.agents.data_sources import fetch_source_data
from src.agents.ingress import IngressAgent
from src.engine.job_history import log_job, get_job_log

logger = logging.getLogger("Scheduler")
scheduler = AsyncIOScheduler()

from src.engine.condenser import Condenser
from src.engine.cognitive import CognitiveService

async def process_data_source(source_id):
    job_id = f"source_{source_id}"
    started = datetime.now(timezone.utc)
    log_job(job_id, f"Data Source {source_id}", "running", started)
    logger.info(f"Processing Data Source: {source_id}")
    db = SessionLocal()
    try:
        source = db.query(DataSource).filter(DataSource.id == source_id).first()
        if not source or not source.enabled:
            log_job(job_id, f"Data Source {source_id}", "skipped", started,
                     datetime.now(timezone.utc))
            return

        content = await fetch_source_data(source)

        import os
        q_host = os.getenv("QDRANT_HOST", "qdrant")
        q_port = int(os.getenv("QDRANT_PORT", 6333))
        qdrant = QdrantClient(host=q_host, port=q_port)

        agent = IngressAgent(db, qdrant)

        from src.db.schemas import EpisodicItemCreate
        mem_data = EpisodicItemCreate(
            project_id=str(source.project_id),
            text=content,
            source=source.source_type,
            metadata={"source_name": source.name, "source_id": str(source.id)}
        )
        new_item = agent.process_memory(mem_data)

        condenser = Condenser(db)
        await condenser.distill(source.project_id, [new_item])

        source.last_run = datetime.utcnow()
        db.commit()
        finished = datetime.now(timezone.utc)
        duration = int((finished - started).total_seconds() * 1000)
        log_job(job_id, source.name, "success", started, finished, duration)
        logger.info(f"Finished processing source {source.name} — {duration}ms")

    except Exception as e:
        finished = datetime.now(timezone.utc)
        duration = int((finished - started).total_seconds() * 1000)
        log_job(job_id, f"Data Source {source_id}", "error", started, finished, duration, str(e))
        logger.error(f"Error processing source {source_id}: {e}")
    finally:
        db.close()

def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started.")
        
        # Add background maintenance jobs
        # 1. Activation Decay (Daily at midnight)
        scheduler.add_job(
            run_decay_task,
            CronTrigger(hour=0, minute=0),
            id="activation_decay",
            replace_existing=True
        )
        logger.info("Scheduled background maintenance jobs.")

async def run_decay_task():
    job_id = "activation_decay"
    started = datetime.now(timezone.utc)
    log_job(job_id, "Activation Decay", "running", started)
    logger.info("Running background activation decay task...")
    db = SessionLocal()
    try:
        cog = CognitiveService(db)
        cog.apply_activation_decay()

        # --- Synapse Engine Decay ---
        from src.synapses.config import synapse_config
        if synapse_config.ENABLED:
            from src.synapses.decay import run_synapse_decay_cycle
            run_synapse_decay_cycle(db)
            
            # --- Periodic Consolidation ---
            # Run consolidation for all projects in background
            from src.db.models import Project
            from src.synapses.consolidation import MemoryConsolidator
            consolidator = MemoryConsolidator(db)
            projects = db.query(Project).all()
            for project in projects:
                await consolidator.run_consolidation_cycle(project.id)

        finished = datetime.now(timezone.utc)
        duration = int((finished - started).total_seconds() * 1000)
        log_job(job_id, "Activation Decay", "success", started, finished, duration)
        logger.info("Activation decay completed.")
    except Exception as e:
        finished = datetime.now(timezone.utc)
        duration = int((finished - started).total_seconds() * 1000)
        log_job(job_id, "Activation Decay", "error", started, finished, duration, str(e))
        logger.error(f"Error in decay task: {e}")
    finally:
        db.close()

def schedule_data_source(data_source: DataSource):
    """
    Schedules or Reschedules a data source job.
    """
    job_id = str(data_source.id)
    
    # Remove existing if any
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        
    if data_source.enabled and data_source.cron_schedule:
        try:
            scheduler.add_job(
                process_data_source,
                CronTrigger.from_crontab(data_source.cron_schedule),
                id=job_id,
                args=[data_source.id],
                replace_existing=True
            )
            logger.info(f"Scheduled job {job_id} with cron: {data_source.cron_schedule}")
        except Exception as e:
            logger.error(f"Failed to schedule job {job_id}: {e}")

def trigger_data_source(data_source_id):
    scheduler.add_job(process_data_source, args=[data_source_id])
    logger.info(f"Triggered immediate job for {data_source_id}")
