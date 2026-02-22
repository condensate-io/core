from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.security import APIKeyHeader, HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from qdrant_client import QdrantClient
from qdrant_client.http import models
from typing import List, Dict, Any, Optional
import uuid
import secrets
import os

from src.db.session import get_db
from src.db.models import Project, EpisodicItem, Assertion, Entity, Relation, ApiKey, DataSource

router = APIRouter()

# --- Qdrant Dependency ---
from src.db.session import get_qdrant # Use centralized dependency

# --- Auth Helper ---
security = HTTPBasic()

def get_api_key(
    api_key_header: str = Depends(APIKeyHeader(name="Authorization", auto_error=False)),
    db: Session = Depends(get_db)
) -> ApiKey:
    if not api_key_header:
        raise HTTPException(status_code=401, detail="Missing API Key")
    clean_key = api_key_header.replace("Bearer ", "").strip()
    key_record = db.query(ApiKey).filter(ApiKey.key == clean_key, ApiKey.is_active == True).first()
    if not key_record:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return key_record

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    import os
    admin_user = os.getenv("ADMIN_USERNAME", "admin")
    admin_pass = os.getenv("ADMIN_PASSWORD", "admin")
    
    is_user_ok = secrets.compare_digest(credentials.username, admin_user)
    is_pass_ok = secrets.compare_digest(credentials.password, admin_pass)
    
    if not (is_user_ok and is_pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@router.get("/check-auth")
def check_auth(user: str = Depends(verify_admin)):
    """
    Simple endpoint to verify credentials.
    Returns 200 OK if verify_admin succeeds.
    """
    return {"status": "authenticated", "user": user}

# --- Stats ---
@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    from src.db.models import Assertion as AssertionModel
    total_projects = db.query(Project).count()
    total_memories = db.query(EpisodicItem).count()
    total_learnings = db.query(Assertion).count()
    total_keys = db.query(ApiKey).count()
    total_entities = db.query(Entity).count()
    total_relations = db.query(Relation).count()
    pending_review = db.query(Assertion).filter(Assertion.status == "pending_review").count()

    return {
        "total_projects": total_projects,
        "total_memories": total_memories,
        "total_learnings": total_learnings,
        "total_keys": total_keys,
        "total_entities": total_entities,
        "total_relations": total_relations,
        "pending_review": pending_review
    }

# --- Job History ---
@router.get("/jobs")
def get_jobs(limit: int = 100):
    """
    Return the in-memory job run history from the scheduler and MCP background tasks.
    Includes data-source pulls, condensation runs, and maintenance jobs.
    """
    from src.engine.scheduler import get_job_log
    return {"jobs": get_job_log()[:limit]}

# --- Keys Management ---
@router.get("/keys")
def get_keys(db: Session = Depends(get_db)):
    keys = db.query(ApiKey).all()
    return [
        {
            "key": k.key,
            "name": k.name,
            "project_id": str(k.project_id),
            "is_active": k.is_active
        }
        for k in keys
    ]

@router.post("/keys")
def create_key(name: str, project_id: str, db: Session = Depends(get_db)):
    # Check if project exists, or create one?
    # For now, we assume project_id string might be a name or ID.
    # Let's try to convert to UUID.
    try:
        pid = uuid.UUID(project_id)
        project = db.query(Project).filter(Project.id == pid).first()
    except ValueError:
        # treat as name, generate UUID
        pid = uuid.uuid5(uuid.NAMESPACE_DNS, project_id)
        project = db.query(Project).filter(Project.id == pid).first()
        
    if not project:
        # Auto-create project
        project = Project(id=pid, name=project_id)
        db.add(project)
        db.commit()
    
    new_key = f"sk-{uuid.uuid4()}"
    api_key = ApiKey(key=new_key, name=name, project_id=pid)
    db.add(api_key)
    db.commit()
    
    return {"key": new_key, "name": name, "project_id": str(pid)}

@router.delete("/keys/{key}")
def delete_key(key: str, db: Session = Depends(get_db)):
    api_key = db.query(ApiKey).filter(ApiKey.key == key).first()
    if api_key:
        db.delete(api_key)
        db.commit()
    return {"status": "deleted"}

# --- Data Sources ---
@router.get("/sources")
def get_sources(db: Session = Depends(get_db)):
    sources = db.query(DataSource).all()
    # Pydantic conversion would be better but doing manual dict for speed
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "project_id": str(s.project_id),
            "type": s.source_type,
            "schedule": s.cron_schedule,
            "enabled": s.enabled,
            "last_run": s.last_run
        }
        for s in sources
    ]

@router.post("/sources")
def create_source(payload: Dict[str, Any], db: Session = Depends(get_db)):
    # payload matches DataSourceCreate schema theoretically
    project_id = payload.get("project_id")
    # Resolve project UUID
    try:
        pid = uuid.UUID(project_id)
    except ValueError:
        pid = uuid.uuid5(uuid.NAMESPACE_DNS, project_id) # Simplify
        
    ds = DataSource(
        project_id=pid,
        name=payload.get("name"),
        source_type=payload.get("source_type"),
        configuration=payload.get("configuration", {}),
        cron_schedule=payload.get("cron_schedule"),
        enabled=payload.get("enabled", True)
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    
    from src.engine.scheduler import schedule_data_source
    schedule_data_source(ds)
    
    return {"id": str(ds.id), "status": "created"}

@router.post("/sources/{source_id}/trigger")
def trigger_source(source_id: str, db: Session = Depends(get_db)):
    from src.engine.scheduler import trigger_data_source
    try:
        sid = uuid.UUID(source_id)
        trigger_data_source(sid)
        return {"status": "triggered"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

# --- Memory Management ---
@router.get("/memories")
def get_memories(limit: int = 100, db: Session = Depends(get_db)):
    # Map EpisodicItem -> Memory view
    memories = db.query(EpisodicItem).order_by(EpisodicItem.created_at.desc()).limit(limit).all()
    return [
        {
            "id": str(m.id),
            "content": m.text, # Mapping text -> content
            "project_id": str(m.project_id),
            "created_at": m.created_at.isoformat(),
            "type": m.source
        }
        for m in memories
    ]

@router.delete("/memories/{memory_id}")
def delete_memory(memory_id: str, db: Session = Depends(get_db), qdrant: QdrantClient = Depends(get_qdrant)):
    try:
        mid = uuid.UUID(memory_id)
        mem = db.query(EpisodicItem).filter(EpisodicItem.id == mid).first()
        if mem:
            # Delete from Postgres
            db.delete(mem)
            db.commit()
            
            # Delete from Qdrant
            try:
                qdrant.delete(
                    collection_name="episodic_chunks",
                    points_selector=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="item_id",
                                match=models.MatchValue(value=str(mid))
                            )
                        ]
                    )
                )
            except Exception as e:
                print(f"Warning: Failed to delete from Qdrant: {e}")
            
            return {"status": "deleted", "id": memory_id}
    except ValueError:
        pass
    raise HTTPException(status_code=404, detail="Memory not found")

@router.post("/memories/prune")
def prune_memories(payload: Dict[str, Any], db: Session = Depends(get_db)):
    query = payload.get("query")
    threshold = payload.get("threshold", 0.7)
    # Placeholder for prune logic (requires embedding query + checking Qdrant)
    return {"message": "Pruning not implemented in V1 port yet."}

# --- Vectors Visualizer ---
@router.get("/vectors")
def get_vectors(visual_multiplier: float = 1.0, db: Session = Depends(get_db)):
    """
    Returns nodes and links for the D3 graph visualization.
    Now includes Entities and Relationships (Co-occurrence + Semantic).
    """
    nodes = []
    links = []
    
    # 1. Fetch Entities (Concepts, Systems, etc.)
    entities = db.query(Entity).limit(500).all()
    for e in entities:
        nodes.append({
            "id": str(e.id),
            "content": e.canonical_name,
            "full_content": f"Entity [{e.type}]: {e.canonical_name}",
            "type": "entity",
            "val": 3, # Larger nodes for entities
            "color": "var(--primary-color)"
        })

    # 2. Fetch Relations (The "Gravity" edges)
    relations = db.query(Relation).limit(1000).all()
    for rel in relations:
        links.append({
            "source": str(rel.from_id),
            "target": str(rel.to_id),
            "value": rel.strength, # Relationship strength drives "gravity" in D3
            "type": rel.relation_type,
            "color": "rgba(255, 255, 255, 0.2)"
        })
        
    # 3. Fetch Memories (Episodic)
    memories = db.query(EpisodicItem).order_by(EpisodicItem.created_at.desc()).limit(100).all()
    for m in memories:
        nodes.append({
            "id": str(m.id),
            "content": m.text[:40] + "...",
            "full_content": m.text,
            "type": "episodic",
            "val": 1
        })
        
    # 4. Fetch Learnings (Assertions)
    assertions = db.query(Assertion).limit(100).all()
    for a in assertions:
        nodes.append({
            "id": str(a.id),
            "content": f"{a.subject_text or 'User'} {a.predicate} {a.object_text or '?'}",
            "full_content": f"Assertion: {a.subject_text or 'User'} {a.predicate} {a.object_text}",
            "type": "semantic",
            "val": 2,
            "provenance": a.provenance
        })
        
        # Evidence Links (Assertion -> Episodic)
        if a.provenance:
            for prov in a.provenance:
                eid = prov.get('episodic_id')
                if eid:
                    links.append({
                        "source": str(a.id),
                        "target": str(eid),
                        "value": 0.5, # Weaker link for evidence
                        "type": "evidence"
                    })
        
        # Semantic Links (Assertion -> Entities)
        if a.subject_entity_id:
            links.append({
                "source": str(a.id),
                "target": str(a.subject_entity_id),
                "value": 1.0,
                "type": "refers_to"
            })
        if a.object_entity_id:
            links.append({
                "source": str(a.id),
                "target": str(a.object_entity_id),
                "value": 1.0,
                "type": "refers_to"
            })
    
    return {"nodes": nodes, "links": links}

class PlaygroundRequest(BaseModel):
    project_id: str
    query: str
    skip_llm: bool = True
    llm_config: Optional[Dict[str, str]] = None

@router.post("/playground/retrieve")
async def playground_retrieve(
    req: PlaygroundRequest,
    db: Session = Depends(get_db),
    qdrant: QdrantClient = Depends(get_qdrant)
):
    """Test the MemoryRouter with a real Qdrant client for vector search."""
    from src.retrieve.router import MemoryRouter
    mr = MemoryRouter(db, qdrant)
    result = await mr.route_and_retrieve(
        req.project_id,
        req.query,
        skip_llm=req.skip_llm,
        llm_config=req.llm_config
    )
    return result


@router.get("/entities")
def get_entities(limit: int = 200, db: Session = Depends(get_db)):
    """List all canonical entities extracted by NER/LLM."""
    entities = db.query(Entity).order_by(Entity.first_seen_at.desc()).limit(limit).all()
    return [
        {
            "id": str(e.id),
            "canonical_name": e.canonical_name,
            "type": e.type,
            "aliases": e.aliases or [],
            "project_id": str(e.project_id),
            "created_at": e.first_seen_at.isoformat() if e.first_seen_at else None,
        }
        for e in entities
    ]

@router.get("/learnings")
def get_learnings(limit: int = 100, db: Session = Depends(get_db)):
    # Map Assertion -> Learning view
    assertions = db.query(Assertion).order_by(Assertion.last_seen_at.desc()).limit(limit).all()
    return [
        {
            "id": str(a.id),
            "statement": f"{a.subject_text or 'User'} {a.predicate} {a.object_text or '?'}",
            "confidence": a.confidence,
            "status": a.status,
            "created_at": a.first_seen_at.isoformat()
        }
        for a in assertions
    ]

# --- File Upload ---
@router.post("/upload")
def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    import shutil
    import os
    
    upload_dir = os.getenv("UPLOAD_DIR", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {"path": file_path, "filename": file.filename}
