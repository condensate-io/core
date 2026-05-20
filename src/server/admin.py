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
import json
import time
import httpx
from datetime import datetime

from src.db.session import get_db
from src.db.models import Project, EpisodicItem, Assertion, Entity, Relation, ApiKey, DataSource

router = APIRouter()


# --- Qdrant Dependency ---
from src.db.session import get_qdrant # Use centralized dependency

# --- Auth Helper ---
security = HTTPBasic()

def get_api_key(
    auth_header: str = Depends(APIKeyHeader(name="Authorization", auto_error=False)),
    x_api_header: str = Depends(APIKeyHeader(name="X-API-Key", auto_error=False)),
    db: Session = Depends(get_db)
) -> ApiKey:
    """
    Look for an API Key in Authorization (Bearer), X-API-Key, 
    or even as a fallback, allow credentials from Basic Auth if provided.
    """
    key_str = auth_header or x_api_header
    
    # 1. Standard API Key Logic
    if key_str:
        clean_key = key_str.replace("Bearer ", "").strip()
        # Fallback check: if it looks like "Basic ...", skip to basic auth logic
        if not key_str.startswith("Basic "):
            key_record = db.query(ApiKey).filter(ApiKey.key == clean_key, ApiKey.is_active == True).first()
            if key_record:
                return key_record

    # 2. Basic Auth Fallback (Admin as Super-User for any project)
    # Since we can't easily use "verify_admin" as a sub-dependency without logic duplication,
    # we manually check for Basic Auth here or return 401.
    if auth_header and auth_header.startswith("Basic "):
        try:
            import base64
            encoded = auth_header.split(" ", 1)[1]
            decoded = base64.b64decode(encoded).decode("utf-8")
            user, pwd = decoded.split(":", 1)
            
            admin_user = os.getenv("ADMIN_USERNAME", "admin")
            admin_pass = os.getenv("ADMIN_PASSWORD", "admin")
            
            if secrets.compare_digest(user, admin_user) and secrets.compare_digest(pwd, admin_pass):
                # Return the primary API key or a placeholder for Admin
                primary = db.query(ApiKey).filter(ApiKey.name == "condensate-primary").first()
                if primary:
                    return primary
        except:
            pass

    raise HTTPException(status_code=401, detail="Missing or Invalid API Key / Credentials")

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
    total_consolidations = 0
    try:
        from src.synapses.models import ConsolidatedMemory
        total_consolidations = db.query(ConsolidatedMemory).count()
    except Exception:
        db.rollback()
        pass
    pending_review = db.query(Assertion).filter(Assertion.status == "pending_review").count()

    return {
        "total_projects": total_projects,
        "total_memories": total_memories,
        "total_learnings": total_learnings,
        "total_keys": total_keys,
        "total_entities": total_entities,
        "total_relations": total_relations,
        "total_consolidations": total_consolidations,
        "pending_review": pending_review
    }

# --- Job History ---
@router.get("/jobs")
def get_jobs(limit: int = 100):
    """
    Return the in-memory job run history from the scheduler and MCP background tasks.
    Includes data-source pulls, condensation runs, and maintenance jobs.
    """
    from src.engine.job_history import get_job_log
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
    key_record = db.query(ApiKey).filter(ApiKey.key == key).first()
    if key_record:
        db.delete(key_record)
        db.commit()
    return {"status": "deleted"}

# --- Projects Management ---
@router.get("/projects")
def get_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).all()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "created_at": p.created_at.isoformat() if p.created_at else None
        }
        for p in projects
    ]

@router.patch("/projects/{project_id}")
def update_project(project_id: str, data: Dict[str, Any], db: Session = Depends(get_db)):
    pid = uuid.UUID(project_id)
    project = db.query(Project).filter(Project.id == pid).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if "name" in data:
        project.name = data["name"]
    db.commit()
    return {"status": "updated"}

@router.delete("/projects/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db), qdrant: QdrantClient = Depends(get_qdrant)):
    pid = uuid.UUID(project_id)
    project = db.query(Project).filter(Project.id == pid).first()
    if project:
        # 1. Delete associated vectors in Qdrant
        try:
            from qdrant_client.http import models
            for collection in ["episodic_chunks", "memories"]:
                try:
                    qdrant.delete(
                        collection_name=collection,
                        points_selector=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="project_id",
                                    match=models.MatchValue(value=str(pid))
                                )
                            ]
                        )
                    )
                except Exception:
                    pass
        except Exception as e:
            print(f"Warning: Failed to delete project vectors from Qdrant: {e}")

        # 2. Delete from DB (cascades to all other child tables)
        db.delete(project)
        db.commit()
    return {"status": "deleted"}

@router.post("/projects/bulk-delete")
def bulk_delete_projects(ids: List[str], db: Session = Depends(get_db)):
    for pid in ids:
        delete_project(pid, db)
    return {"status": "bulk_deleted", "count": len(ids)}

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

@router.get("/memories")
def get_memories(
    limit: int = 100, 
    project_id: Optional[str] = None, 
    api_key_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    # Map EpisodicItem -> Memory view
    query = db.query(EpisodicItem)
    
    if project_id:
        try:
            pid = uuid.UUID(project_id)
            query = query.filter(EpisodicItem.project_id == pid)
        except ValueError:
            pass # ignore invalid UUIDs
            
    if api_key_name:
        # Resolve project IDs associated with this key name
        project_ids = [k.project_id for k in db.query(ApiKey).filter(ApiKey.name == api_key_name).all()]
        if project_ids:
            query = query.filter(EpisodicItem.project_id.in_(project_ids))
        else:
            # If no project IDs found for this key name, return empty result to satisfy the filter
            return []
            
    memories = query.order_by(EpisodicItem.created_at.desc()).limit(limit).all()
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

@router.patch("/memories/{memory_id}")
def update_memory(memory_id: str, data: Dict[str, Any], db: Session = Depends(get_db)):
    mid = uuid.UUID(memory_id)
    mem = db.query(EpisodicItem).filter(EpisodicItem.id == mid).first()
    if not mem:
        raise HTTPException(status_code=404, detail="Memory not found")
    if "content" in data:
        mem.text = data["content"]
    if "type" in data:
        mem.source = data["type"]
    db.commit()
    return {"status": "updated"}

@router.post("/memories/bulk-delete")
def bulk_delete_memories(ids: List[str], db: Session = Depends(get_db), qdrant: QdrantClient = Depends(get_qdrant)):
    for mid in ids:
        delete_memory(mid, db, qdrant)
    return {"status": "bulk_deleted", "count": len(ids)}

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
def get_vectors(project_id: Optional[str] = None, visual_multiplier: float = 1.0, db: Session = Depends(get_db)):
    """
    Returns nodes and links for the D3 graph visualization.
    Now supports project-specific filtering for OmniSim simulations.
    """
    nodes = []
    links = []
    
    # Filter by project if provided
    pid = None
    if project_id:
        try:
            pid = uuid.UUID(project_id)
        except ValueError:
            pass

    # 1. Fetch Entities (Concepts, Systems, etc.)
    q_entities = db.query(Entity)
    if pid:
        q_entities = q_entities.filter(Entity.project_id == pid)
    entities = q_entities.limit(500).all()
    
    # Type -> Color mapping for OmniSim
    type_colors = {
        "Agent": "#60a5fa",     # Blue
        "Citizen": "#34d399",   # Emerald
        "Policy": "#fbbf24",    # Amber
        "Resource": "#f472b6",  # Pink
        "Location": "#a78bfa",  # Purple
        "System": "#94a3b8"     # Slate
    }
    
    for e in entities:
        nodes.append({
            "id": str(e.id),
            "content": e.canonical_name,
            "full_content": f"Entity [{e.type}]: {e.canonical_name}",
            "type": "entity",
            "subtype": e.type,
            "val": 4, # Larger nodes for entities
            "color": type_colors.get(e.type, "var(--primary-color)")
        })

    # 2. Fetch Relations (The "Gravity" edges)
    q_relations = db.query(Relation)
    if pid:
        q_relations = q_relations.filter(Relation.project_id == pid)
    relations = q_relations.limit(1000).all()
    
    for rel in relations:
        links.append({
            "source": str(rel.from_id),
            "target": str(rel.to_id),
            "value": rel.strength * visual_multiplier, 
            "type": rel.relation_type,
            "color": "rgba(255, 255, 255, 0.15)"
        })
        
    # 3. Fetch Memories (Episodic) - Simulation Events
    q_memories = db.query(EpisodicItem)
    if pid:
        q_memories = q_memories.filter(EpisodicItem.project_id == pid)
    memories = q_memories.order_by(EpisodicItem.created_at.desc()).limit(150).all()
    
    for m in memories:
        nodes.append({
            "id": str(m.id),
            "content": m.text[:50] + "...",
            "full_content": m.text,
            "type": "episodic",
            "val": 1.5,
            "color": "#475569" # Simulation event gray
        })
        
    # 4. Fetch Learnings (Assertions) - Discovered Facts
    q_assertions = db.query(Assertion)
    if pid:
        q_assertions = q_assertions.filter(Assertion.project_id == pid)
    assertions = q_assertions.limit(200).all()
    
    for a in assertions:
        nodes.append({
            "id": str(a.id),
            "content": f"{a.subject_text or 'User'} {a.predicate} {a.object_text or '?'}",
            "full_content": f"Assertion: {a.subject_text or 'User'} {a.predicate} {a.object_text}",
            "type": "semantic",
            "val": 2.5,
            "provenance": a.provenance,
            "color": "#f87171" # Fact Red
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
                        "type": "evidence",
                        "color": "rgba(248, 113, 113, 0.2)"
                    })
        
        # Semantic Links (Assertion -> Entities)
        if a.subject_entity_id:
            links.append({
                "source": str(a.id),
                "target": str(a.subject_entity_id),
                "value": 1.0,
                "type": "subject_of",
                "color": "rgba(96, 165, 250, 0.3)"
            })
        if a.object_entity_id:
            links.append({
                "source": str(a.id),
                "target": str(a.object_entity_id),
                "value": 1.0,
                "type": "object_of",
                "color": "rgba(96, 165, 250, 0.3)"
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
def get_entities(
    limit: int = 200, 
    project_id: Optional[str] = None,
    api_key_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all canonical entities extracted by NER/LLM."""
    query = db.query(Entity)
    
    if project_id:
        try:
            pid = uuid.UUID(project_id)
            query = query.filter(Entity.project_id == pid)
        except ValueError:
            pass
            
    if api_key_name:
        project_ids = [k.project_id for k in db.query(ApiKey).filter(ApiKey.name == api_key_name).all()]
        query = query.filter(Entity.project_id.in_(project_ids))

    entities = query.order_by(Entity.first_seen_at.desc()).limit(limit).all()
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

@router.patch("/entities/{entity_id}")
def update_entity(entity_id: str, data: Dict[str, Any], db: Session = Depends(get_db)):
    eid = uuid.UUID(entity_id)
    entity = db.query(Entity).filter(Entity.id == eid).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    if "canonical_name" in data:
        entity.canonical_name = data["canonical_name"]
    if "type" in data:
        entity.type = data["type"]
    if "aliases" in data:
        entity.aliases = data["aliases"]
    db.commit()
    return {"status": "updated"}

@router.delete("/entities/{entity_id}")
def delete_entity(entity_id: str, db: Session = Depends(get_db)):
    eid = uuid.UUID(entity_id)
    entity = db.query(Entity).filter(Entity.id == eid).first()
    if entity:
        # 1. Null out references in assertions to avoid FK violation (if CASCADE not set)
        db.query(Assertion).filter(Assertion.subject_entity_id == eid).update({"subject_entity_id": None})
        db.query(Assertion).filter(Assertion.object_entity_id == eid).update({"object_entity_id": None})
        
        # 2. Delete relations involving this entity (dangling entries)
        from src.db.models import Relation
        db.query(Relation).filter((Relation.from_id == eid) | (Relation.to_id == eid)).delete()
        
        db.delete(entity)
        db.commit()
    return {"status": "deleted"}

@router.post("/entities/bulk-delete")
def bulk_delete_entities(ids: List[str], db: Session = Depends(get_db)):
    for eid in ids:
        delete_entity(eid, db)
    return {"status": "bulk_deleted", "count": len(ids)}

@router.get("/learnings")
def get_learnings(
    limit: int = 100, 
    project_id: Optional[str] = None,
    api_key_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    # Map Assertion -> Learning view
    query = db.query(Assertion)
    
    if project_id:
        try:
            pid = uuid.UUID(project_id)
            query = query.filter(Assertion.project_id == pid)
        except ValueError:
            pass
            
    if api_key_name:
        project_ids = [k.project_id for k in db.query(ApiKey).filter(ApiKey.name == api_key_name).all()]
        query = query.filter(Assertion.project_id.in_(project_ids))

    assertions = query.order_by(Assertion.last_seen_at.desc()).limit(limit).all()
    return [
        {
            "id": str(a.id),
            "subject_text": a.subject_text,
            "predicate": a.predicate,
            "object_text": a.object_text,
            "statement": f"{a.subject_text or 'User'} {a.predicate} {a.object_text or '?'}",
            "confidence": a.confidence,
            "status": a.status,
            "created_at": a.first_seen_at.isoformat()
        }
        for a in assertions
    ]

@router.get("/consolidations")
def get_consolidations(
    limit: int = 100, 
    project_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    from src.synapses.models import ConsolidatedMemory
    query = db.query(ConsolidatedMemory)
    
    if project_id:
        try:
            pid = uuid.UUID(project_id)
            query = query.filter(ConsolidatedMemory.project_id == pid)
        except ValueError:
            pass
            
    items = query.order_by(ConsolidatedMemory.created_at.desc()).limit(limit).all()
    return [
        {
            "id": str(i.id),
            "content": i.content,
            "project_id": str(i.project_id),
            "confidence": i.confidence,
            "created_at": i.created_at.isoformat(),
            "evidence_count": len(i.evidence_ids) if i.evidence_ids else 0
        }
        for i in items
    ]

@router.patch("/learnings/{assertion_id}")
def update_learning(assertion_id: str, data: Dict[str, Any], db: Session = Depends(get_db)):
    aid = uuid.UUID(assertion_id)
    assertion = db.query(Assertion).filter(Assertion.id == aid).first()
    if not assertion:
        raise HTTPException(status_code=404, detail="Assertion not found")
    if "subject_text" in data:
        assertion.subject_text = data["subject_text"]
    if "predicate" in data:
        assertion.predicate = data["predicate"]
    if "object_text" in data:
        assertion.object_text = data["object_text"]
    if "status" in data:
        assertion.status = data["status"]
    db.commit()
    return {"status": "updated"}

@router.delete("/learnings/{assertion_id}")
def delete_learning(assertion_id: str, db: Session = Depends(get_db)):
    aid = uuid.UUID(assertion_id)
    assertion = db.query(Assertion).filter(Assertion.id == aid).first()
    if assertion:
        db.delete(assertion)
        db.commit()
    return {"status": "deleted"}

@router.post("/learnings/bulk-delete")
def bulk_delete_learnings(ids: List[str], db: Session = Depends(get_db)):
    for aid in ids:
        delete_learning(aid, db)
    return {"status": "bulk_deleted", "count": len(ids)}

# --- Relations Management ---
@router.get("/relations")
def get_relations(limit: int = 200, db: Session = Depends(get_db)):
    relations = db.query(Relation).limit(limit).all()
    return [
        {
            "id": str(r.id),
            "from_id": str(r.from_id),
            "to_id": str(r.to_id),
            "relation_type": r.relation_type,
            "strength": r.strength,
            "project_id": str(r.project_id)
        }
        for r in relations
    ]

@router.patch("/relations/{relation_id}")
def update_relation(relation_id: str, data: Dict[str, Any], db: Session = Depends(get_db)):
    rid = uuid.UUID(relation_id)
    rel = db.query(Relation).filter(Relation.id == rid).first()
    if not rel:
        raise HTTPException(status_code=404, detail="Relation not found")
    if "relation_type" in data:
        rel.relation_type = data["relation_type"]
    if "strength" in data:
        rel.strength = data["strength"]
    db.commit()
    return {"status": "updated"}

@router.delete("/relations/{relation_id}")
def delete_relation(relation_id: str, db: Session = Depends(get_db)):
    rid = uuid.UUID(relation_id)
    rel = db.query(Relation).filter(Relation.id == rid).first()
    if rel:
        db.delete(rel)
        db.commit()
    return {"status": "deleted"}

@router.post("/relations/bulk-delete")
def bulk_delete_relations(ids: List[str], db: Session = Depends(get_db)):
    for rid in ids:
        delete_relation(rid, db)
    return {"status": "bulk_deleted", "count": len(ids)}

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
# --- LLM Config ---
CONFIG_FILE = "llm_config.json"

@router.get("/config/llm")
def get_llm_config():
    import json
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
             pass
    
    # Default if no file or error
    default_config = {
        "id": "default",
        "name": "Default Config",
        "baseUrl": os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
        "model": os.getenv("LLM_MODEL", "phi3"),
        "apiKey": os.getenv("LLM_API_KEY", "ollama"),
        "is_active": True,
        "is_primary": True
    }
    return {"configs": [default_config]}

@router.post("/config/llm/save")
def save_llm_configs(data: Dict[str, Any], user: str = Depends(verify_admin)):
    import json
    configs = data.get("configs", [])
    # Validation: Ensure at most one primary
    primary_count = sum(1 for c in configs if c.get("is_primary"))
    if primary_count > 1:
        raise HTTPException(status_code=400, detail="Only one configuration can be primary.")
    
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({"configs": configs}, f, indent=2)
    except Exception as e:
        print(f"CRITICAL: Failed to write to {CONFIG_FILE}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to write config file: {e}")
    
    # Update environment variables for the primary one for legacy/system compatibility
    primary = next((c for c in configs if c.get("is_primary")), None)
    if primary:
        os.environ["LLM_BASE_URL"] = primary.get("baseUrl", "")
        os.environ["LLM_MODEL"] = primary.get("model", "")
        os.environ["LLM_API_KEY"] = primary.get("apiKey", "")
    
    return {"status": "saved", "count": len(configs)}

@router.post("/projects/{project_id}/condense")
async def manual_condense(project_id: str, db: Session = Depends(get_db)):
    """Trigger condensation for all episodic memories in a project."""
    from src.engine.condenser import Condenser
    try:
        pid = uuid.UUID(project_id)
        # Fetch all episodic items for this project
        items = db.query(EpisodicItem).filter(EpisodicItem.project_id == pid).all()
        if not items:
            return {"status": "skipped", "message": "No episodic items found for this project."}
        
        condenser = Condenser(db)
        await condenser.distill(pid, items)
        return {"status": "success", "count": len(items)}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project UUID")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_id}/consolidate")
async def manual_consolidate(project_id: str, db: Session = Depends(get_db)):
    """Trigger the consolidation cycle manually for a project."""
    from src.synapses.consolidation import MemoryConsolidator
    try:
        pid = uuid.UUID(project_id)
        consolidator = MemoryConsolidator(db)
        await consolidator.run_consolidation_cycle(pid)
        return {"status": "success"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project UUID")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/config/llm/test")
async def test_llm_config(config: Dict[str, Any], user: str = Depends(verify_admin)):
    import time
    import httpx
    base_url = config.get("baseUrl")
    model = config.get("model")
    api_key = config.get("apiKey")
    
    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Simple chat completion attempt
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "hi"}]
            }
            
            # Adaptive parameter handling for newer OpenAI models (o1, nano, etc.)
            if any(m in model.lower() for m in ["o1-", "o3-", "nano"]):
                payload["max_completion_tokens"] = 10
            else:
                payload["max_tokens"] = 5
                
            response = await client.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"}
            )
            response.raise_for_status()
            latency = (time.time() - start_time) * 1000 # ms
            return {"status": "success", "latency": round(latency, 1)}
    except httpx.HTTPStatusError as e:
        latency = (time.time() - start_time) * 1000
        error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
        return {"status": "error", "error": error_msg, "latency": round(latency, 1)}
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        return {"status": "error", "error": str(e), "latency": round(latency, 1)}

# --- System Config ---
SYSTEM_CONFIG_FILE = "system_config.json"

@router.get("/config/system")
def get_system_config():
    if os.path.exists(SYSTEM_CONFIG_FILE):
        try:
            with open(SYSTEM_CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    
    return {
        "review_mode": os.getenv("REVIEW_MODE", "manual").lower()
    }

@router.post("/config/system")
def save_system_config(data: Dict[str, Any], user: str = Depends(verify_admin)):
    with open(SYSTEM_CONFIG_FILE, "w") as f:
        json.dump(data, f)
    
    if "review_mode" in data:
        os.environ["REVIEW_MODE"] = data["review_mode"]
    
    return {"status": "saved", "config": data}

# --- Synapse Config ---
SYNAPSE_CONFIG_FILE = "synapse_config.json"

@router.get("/config/synapse")
def get_synapse_config():
    from src.synapses.config import synapse_config
    # Refresh to ensure we have latest from file
    synapse_config.refresh()
    return {
        "enabled": synapse_config.ENABLED,
        "learning_rate": synapse_config.LEARNING_RATE,
        "decay_rate": synapse_config.DECAY_RATE,
        "prune_threshold": synapse_config.PRUNE_THRESHOLD,
        "consolidation_threshold": synapse_config.CONSOLIDATION_THRESHOLD,
        "decay_interval_hours": synapse_config.DECAY_INTERVAL_HOURS
    }

@router.post("/config/synapse")
def save_synapse_config(data: Dict[str, Any], user: str = Depends(verify_admin)):
    with open(SYNAPSE_CONFIG_FILE, "w") as f:
        json.dump(data, f)
    
    from src.synapses.config import synapse_config
    synapse_config.refresh()
    
    return {"status": "saved", "config": data}

# --- Assertion Review Queue ---
@router.get("/review/assertions/pending")
def get_pending_assertions(
    min_instruction_score: float = 0.0,
    min_safety_score: float = 0.0,
    db: Session = Depends(get_db)
):
    """
    Fetch assertions that are pending_review, filtered by guardrail scores.
    """
    query = db.query(Assertion).filter(Assertion.status == "pending_review")
    if min_instruction_score > 0:
        query = query.filter(Assertion.instruction_score >= min_instruction_score)
    if min_safety_score > 0:
        query = query.filter(Assertion.safety_score >= min_safety_score)
    
    assertions = query.order_by(Assertion.first_seen_at.desc()).all()
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
                "status": a.status,
                "first_seen_at": a.first_seen_at.isoformat()
            }
            for a in assertions
        ]
    }

@router.post("/review/assertions/{assertion_id}/approve")
def approve_assertion(assertion_id: str, data: Dict[str, Any], db: Session = Depends(get_db)):
    """Approve an extracted assertion, making it active in the memory graph."""
    try:
        aid = uuid.UUID(assertion_id)
        assertion = db.query(Assertion).filter(Assertion.id == aid).first()
        if not assertion:
            raise HTTPException(status_code=404, detail="Assertion not found")
        
        assertion.status = "approved" # Will be treated as 'active' by retrieval
        assertion.reviewed_by = data.get("reviewed_by", "admin")
        assertion.reviewed_at = datetime.utcnow()
        db.commit()
        return {"status": "approved", "id": assertion_id}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid assertion UUID")

@router.post("/review/assertions/{assertion_id}/reject")
def reject_assertion(assertion_id: str, data: Dict[str, Any], db: Session = Depends(get_db)):
    """Reject an assertion, preventing it from entering the memory graph."""
    try:
        aid = uuid.UUID(assertion_id)
        assertion = db.query(Assertion).filter(Assertion.id == aid).first()
        if not assertion:
            raise HTTPException(status_code=404, detail="Assertion not found")
        
        assertion.status = "rejected"
        assertion.reviewed_by = data.get("reviewed_by", "admin")
        assertion.reviewed_at = datetime.utcnow()
        assertion.rejection_reason = data.get("rejection_reason")
        db.commit()
        return {"status": "rejected", "id": assertion_id}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid assertion UUID")

@router.post("/review/assertions/bulk-approve")
def bulk_approve_assertions(data: Dict[str, Any], db: Session = Depends(get_db)):
    """Approve a list of assertions at once."""
    ids = data.get("assertion_ids", [])
    reviewed_by = data.get("reviewed_by", "admin")
    now = datetime.utcnow()
    
    try:
        uuid_ids = [uuid.UUID(i) for i in ids]
        db.query(Assertion).filter(Assertion.id.in_(uuid_ids)).update({
            "status": "approved",
            "reviewed_by": reviewed_by,
            "reviewed_at": now
        }, synchronize_session=False)
        db.commit()
        return {"status": "bulk_approved", "count": len(ids)}
    except ValueError:
        raise HTTPException(status_code=400, detail="One or more invalid UUIDs provided")
