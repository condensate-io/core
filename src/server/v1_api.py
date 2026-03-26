from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from typing import List, Optional
from src.db.session import get_db, QDRANT_URL, QDRANT_API_KEY
from src.db.models import EpisodicItem, Entity, Assertion, Project, Relation, OntologyNode, ApiKey
from src.db.schemas import (
    ProjectCreate, ProjectResponse,
    EntityCreate, EntityResponse,
    RelationCreate, RelationResponse,
    OntologyCreate, OntologyNodeResponse,
    EpisodicBulkCreate, EpisodicItemCreate,
    GraphCreate
)
from src.agents.ingress import IngressAgent
from qdrant_client import QdrantClient
import uuid

router = APIRouter(prefix="/v1", tags=["v1"])

# --- Project API ---

@router.post("/projects", response_model=ProjectResponse)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(name=data.name)
    db.add(project)
    db.flush()
    
    if data.api_key_name:
        ak = ApiKey(key=str(uuid.uuid4()), name=data.api_key_name, project_id=project.id)
        db.add(ak)
        
    db.commit()
    db.refresh(project)
    return project

@router.get("/projects", response_model=List[ProjectResponse])
def get_projects(limit: int = 100, db: Session = Depends(get_db)):
    stmt = select(Project).limit(limit)
    return db.execute(stmt).scalars().all()

@router.delete("/projects/{project_id}")
def delete_project(project_id: uuid.UUID, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return {"status": "ok"}

# --- Episodic API ---

@router.get("/episodic")
def get_episodic_items(
    project_id: Optional[List[str]] = Query(None), 
    api_key_name: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 100, 
    offset: int = 0,
    db: Session = Depends(get_db)
):
    stmt = select(EpisodicItem)
    
    if project_id:
        if isinstance(project_id, list):
            stmt = stmt.where(EpisodicItem.project_id.in_(project_id))
        else:
            stmt = stmt.where(EpisodicItem.project_id == project_id)
        
    if api_key_name:
        # Resolve project IDs associated with this key name
        project_ids = db.execute(select(ApiKey.project_id).where(ApiKey.name == api_key_name)).scalars().all()
        if project_ids:
            stmt = stmt.where(EpisodicItem.project_id.in_(project_ids))
        else:
            return [] # No projects found for this key name
            
    if source:
        stmt = stmt.where(EpisodicItem.source == source)
    
    stmt = stmt.order_by(EpisodicItem.occurred_at.desc()).limit(limit).offset(offset)
    items = db.execute(stmt).scalars().all()
    
    return [
        {
            "id": str(i.id),
            "project_id": str(i.project_id),
            "source": i.source,
            "text": i.text,
            "occurred_at": i.occurred_at,
            "metadata": i.metadata_
        }
        for i in items
    ]

@router.post("/episodic/bulk")
async def bulk_ingest(data: EpisodicBulkCreate, background_tasks: BackgroundTasks):
    """
    Ingest many events at once (simulation rounds produce batches).
    """
    # Just queue the task
    background_tasks.add_task(run_bulk_ingest, data)
    
    return {"status": "queued", "count": len(data.episodes)}

async def run_bulk_ingest(data: EpisodicBulkCreate):
    from src.db.session import SessionLocal, QDRANT_URL, QDRANT_API_KEY
    from src.agents.ingress import IngressAgent
    from qdrant_client import QdrantClient
    
    db = SessionLocal()
    q_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    try:
        ingress = IngressAgent(db, q_client)
        await ingress.process_and_condense_batch(data.episodes)
    except Exception as e:
        import logging
        logging.getLogger("BulkIngest").error(f"Bulk ingestion failed: {e}")
    finally:
        db.close()

# --- Graph API ---

@router.post("/graph/create")
def create_graph(data: GraphCreate, db: Session = Depends(get_db)):
    # OmniSim needs: POST /v1/graph/create { project_id, name }
    # Since Condensate does not have a separate graph resource yet, 
    # we use projects as graph scopes.
    project_id = data.project_id
    name = data.name
    
    if project_id:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"id": str(project.id), "name": project.name, "status": "existing"}
    
    # Otherwise create new project
    project = Project(name=name)
    db.add(project)
    db.flush()
    
    if data.api_key_name:
        ak = ApiKey(key=str(uuid.uuid4()), name=data.api_key_name, project_id=project.id)
        db.add(ak)
        
    db.commit()
    db.refresh(project)
    return {"id": str(project.id), "name": project.name, "status": "created"}

@router.post("/graph/entities")
def create_entity(data: EntityCreate, db: Session = Depends(get_db)):
    entity = Entity(
        project_id=data.project_id,
        canonical_name=data.name,
        type=data.type,
        aliases=data.aliases or [],
        confidence=data.confidence or 1.0
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return {
        "id": str(entity.id),
        "name": entity.canonical_name,
        "type": entity.type
    }

@router.get("/graph/entities")
def get_entities(
    project_id: Optional[List[str]] = Query(None),
    type: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    stmt = select(Entity)
    if project_id:
        if isinstance(project_id, list):
            stmt = stmt.where(Entity.project_id.in_(project_id))
        else:
            stmt = stmt.where(Entity.project_id == project_id)
    if type:
        stmt = stmt.where(Entity.type == type)
        
    stmt = stmt.limit(limit)
    entities = db.execute(stmt).scalars().all()
    
    return [
        {
            "id": str(e.id),
            "project_id": str(e.project_id),
            "name": e.canonical_name,
            "type": e.type,
            "aliases": e.aliases,
            "confidence": e.confidence
        }
        for e in entities
    ]

@router.post("/graph/relations")
def create_relation(data: RelationCreate, db: Session = Depends(get_db)):
    relation = Relation(
        project_id=data.project_id,
        from_id=data.from_id,
        from_kind=data.from_kind or "entity",
        to_id=data.to_id,
        to_kind=data.to_kind or "entity",
        relation_type=data.relation_type,
        confidence=data.confidence or 1.0
    )
    db.add(relation)
    db.commit()
    db.refresh(relation)
    return {"id": str(relation.id)}

@router.get("/graph/relations")
def get_relations(
    project_id: Optional[List[str]] = Query(None),
    entity_id: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    stmt = select(Relation)
    if project_id:
        if isinstance(project_id, list):
            stmt = stmt.where(Relation.project_id.in_(project_id))
        else:
            stmt = stmt.where(Relation.project_id == project_id)
    if entity_id:
        # Search for relations where entity is either source or target
        stmt = stmt.where(or_(Relation.from_id == entity_id, Relation.to_id == entity_id))
        
    stmt = stmt.limit(limit)
    relations = db.execute(stmt).scalars().all()
    
    return [
        {
            "id": str(r.id),
            "project_id": str(r.project_id),
            "from_id": str(r.from_id),
            "from_kind": r.from_kind,
            "relation_type": r.relation_type,
            "to_id": str(r.to_id),
            "to_kind": r.to_kind,
            "confidence": r.confidence,
            "provenance": r.provenance
        }
        for r in relations
    ]

@router.post("/graph/ontology")
def update_ontology(data: OntologyCreate, db: Session = Depends(get_db)):
    """
    Update or create multiple ontology nodes at once.
    """
    for label in data.entity_types:
        # Check if exists
        exists = db.query(OntologyNode).filter(
            OntologyNode.project_id == data.project_id,
            OntologyNode.label == label,
            OntologyNode.node_type == "entity_type"
        ).first()
        if not exists:
            node = OntologyNode(
                project_id=data.project_id,
                label=label,
                node_type="entity_type",
                confidence=1.0
            )
            db.add(node)
            
    for label in data.edge_types:
        exists = db.query(OntologyNode).filter(
            OntologyNode.project_id == data.project_id,
            OntologyNode.label == label,
            OntologyNode.node_type == "edge_type"
        ).first()
        if not exists:
            node = OntologyNode(
                project_id=data.project_id,
                label=label,
                node_type="edge_type",
                confidence=1.0
            )
            db.add(node)
            
    db.commit()
    return {"status": "ok"}

@router.get("/graph/ontology")
def get_ontology(project_id: uuid.UUID, db: Session = Depends(get_db)):
    stmt = select(OntologyNode).where(OntologyNode.project_id == project_id)
    nodes = db.execute(stmt).scalars().all()
    
    entity_types = [n.label for n in nodes if n.node_type == "entity_type"]
    edge_types = [n.label for n in nodes if n.node_type == "edge_type"]
    
    return {
        "project_id": str(project_id),
        "entity_types": entity_types,
        "edge_types": edge_types
    }

@router.get("/graph/assertions")
def get_assertions(
    project_id: Optional[List[str]] = Query(None),
    subject: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    stmt = select(Assertion)
    if project_id:
        if isinstance(project_id, list):
            stmt = stmt.where(Assertion.project_id.in_(project_id))
        else:
            stmt = stmt.where(Assertion.project_id == project_id)
    if subject:
        # Check if subject is a UUID (meaning entity_id) or text
        try:
            sid = uuid.UUID(subject)
            stmt = stmt.where(or_(Assertion.subject_entity_id == sid, Assertion.object_entity_id == sid))
        except ValueError:
            stmt = stmt.where(Assertion.subject_text.ilike(f"%{subject}%"))
        
    stmt = stmt.limit(limit)
    assertions = db.execute(stmt).scalars().all()
    
    return [
        {
            "id": str(a.id),
            "project_id": str(a.project_id),
            "subject": a.subject_text,
            "subject_id": str(a.subject_entity_id) if a.subject_entity_id else None,
            "predicate": a.predicate,
            "object": a.object_text,
            "object_id": str(a.object_entity_id) if a.object_entity_id else None,
            "confidence": a.confidence,
            "status": a.status,
            "provenance": a.provenance
        }
        for a in assertions
    ]

# --- Export API ---

@router.get("/export/jsonl")
def export_jsonl(project_id: str, db: Session = Depends(get_db)):
    # Streaming response would be better for large datasets, 
    # but for MVP returning a line-delimited string or list
    
    # 1. Fetch all items
    items = db.execute(select(EpisodicItem).where(EpisodicItem.project_id == project_id)).scalars().all()
    
    # 2. Fetch all assertions
    assertions = db.execute(select(Assertion).where(Assertion.project_id == project_id)).scalars().all()
    
    import json
    lines = []
    
    for i in items:
        lines.append(json.dumps({
            "type": "episodic_item",
            "id": str(i.id),
            "text": i.text,
            "source": i.source,
            "created_at": i.created_at.isoformat()
        }))
        
    for a in assertions:
        lines.append(json.dumps({
            "type": "assertion",
            "id": str(a.id),
            "statement": f"{a.subject_text} {a.predicate} {a.object_text}",
            "confidence": a.confidence,
            "provenance": a.provenance
        }))
        
    from fastapi.responses import Response
    return Response(content="\n".join(lines), media_type="application/x-jsonlines")
