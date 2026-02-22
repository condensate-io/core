import sqlite3
import uuid
import os
import logging
from typing import List, Dict, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from qdrant_client import QdrantClient
from qdrant_client.http import models

from src.db.models import Base, Project, Memory, Learning, OntologyNode, OntologyEdge, ApiKey
from src.db.session import engine, SessionLocal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Bootstrap")

# Paths
LOCALMEMCP_PATH = os.getenv("LOCALMEMCP_PATH", "/app/localmemcp_data") # Mount this in docker
SQLITE_DB_PATH = os.path.join(LOCALMEMCP_PATH, "metadata.db")

# Old Qdrant (Assume running on host or accessible network)
OLD_QDRANT_HOST = os.getenv("OLD_QDRANT_HOST", "host.docker.internal")
OLD_QDRANT_PORT = int(os.getenv("OLD_QDRANT_PORT", 6333))

# New Qdrant
NEW_QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
NEW_QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))

def migrate_sqlite_to_postgres(db_session):
    """
    Reads API Keys from SQLite and creates Projects in Postgres.
    """
    if not os.path.exists(SQLITE_DB_PATH):
        logger.warning(f"Metadata DB not found at {SQLITE_DB_PATH}. Skipping SQLite migration.")
        return

    logger.info(f"Migrating data from {SQLITE_DB_PATH}...")
    
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT key, name, project_id, is_active FROM api_keys")
        rows = cursor.fetchall()
        
        for row in rows:
            key, name, project_id_str, is_active = row
            
            # Check if project exists
            # We assume the project_id in SQLite is a UUID string. 
            # If not, we might need to generate one or hash it.
            try:
                project_uuid = uuid.UUID(project_id_str)
            except ValueError:
                # If project_id is not a UUID (e.g. "global"), generate a deterministic UUID
                project_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, project_id_str)
            
            project = db_session.query(Project).filter(Project.id == project_uuid).first()
            if not project:
                project = Project(
                    id=project_uuid,
                    name=project_id_str if name == "Default Global" else name,
                    settings={}
                )
                db_session.add(project)
                logger.info(f"Created Project: {project.name} ({project.id})")
            
            # Create ApiKey
            existing_key = db_session.query(ApiKey).filter(ApiKey.key == key).first()
            if not existing_key:
                api_key = ApiKey(key=key, name=name, project_id=project_uuid, is_active=is_active)
                db_session.add(api_key)
                logger.info(f"Migrated API Key: {name}")
        
        db_session.commit()
    except Exception as e:
        logger.error(f"Error reading SQLite: {e}")
    finally:
        conn.close()

def migrate_memories(db_session):
    """
    Connects to Old Qdrant, fetches memories, inserts into Postgres + New Qdrant.
    """
    try:
        old_client = QdrantClient(host=OLD_QDRANT_HOST, port=OLD_QDRANT_PORT, timeout=10)
        new_client = QdrantClient(host=NEW_QDRANT_HOST, port=NEW_QDRANT_PORT, timeout=10)
        
        # Check connection
        old_client.get_collections()
        logger.info(f"Connected to Old Qdrant at {OLD_QDRANT_HOST}:{OLD_QDRANT_PORT}")
        
    except Exception as e:
        logger.warning(f"Could not connect to Old Qdrant: {e}. Skipping memory migration.")
        return

    # Ensure new collection exists
    if not new_client.collection_exists("memories"):
        new_client.create_collection(
            collection_name="memories",
            vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
        )

    # Scroll old memories
    try:
        LIMIT = 100
        offset = None
        
        while True:
            scroll_result, next_offset = old_client.scroll(
                collection_name="memories",
                limit=LIMIT,
                offset=offset,
                with_payload=True,
                with_vectors=True
            )
            
            for point in scroll_result:
                payload = point.payload
                vector = point.vector
                
                # Get Project UUID
                project_id_str = payload.get("project_id", "global")
                try:
                    project_uuid = uuid.UUID(project_id_str)
                except ValueError:
                    project_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, project_id_str)
                
                # Verify project exists in DB
                project = db_session.query(Project).filter(Project.id == project_uuid).first()
                if not project:
                    # Lazy create project if missed by SQLite migration
                    project = Project(id=project_uuid, name=f"Migrated-{project_id_str}")
                    db_session.add(project)
                    db_session.commit()

                # Create Memory in Postgres
                mem_id = uuid.UUID(point.id) if isinstance(point.id, str) else uuid.uuid4()
                
                # Check if memory exists
                existing_mem = db_session.query(Memory).filter(Memory.id == mem_id).first()
                if not existing_mem:
                    memory = Memory(
                        id=mem_id,
                        project_id=project_uuid,
                        source_type=payload.get("type", "episodic"),
                        content=payload.get("content", ""),
                        vector_id=mem_id, # Re-use same ID for vector
                        processing_state="migrated"
                    )
                    db_session.add(memory)
                    
                    # Upsert to New Qdrant
                    new_client.upsert(
                        collection_name="memories",
                        points=[
                            models.PointStruct(
                                id=str(mem_id),
                                vector=vector,
                                payload=payload
                            )
                        ]
                    )
            
            db_session.commit()
            logger.info(f"Migrated batch of {len(scroll_result)} memories.")
            
            offset = next_offset
            if offset is None:
                break
                
    except Exception as e:
        logger.error(f"Error during memory migration: {e}")


if __name__ == "__main__":
    logger.info("Starting Bootstrap...")
    
    # Init DB
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    
    try:
        migrate_sqlite_to_postgres(session)
        migrate_memories(session)
    finally:
        session.close()
    
    logger.info("Bootstrap complete.")
