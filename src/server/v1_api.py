import uuid
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from qdrant_client import QdrantClient
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.agents.ingress import IngressAgent
from src.db.models import (
    ApiKey,
    Assertion,
    Entity,
    EpisodicItem,
    OntologyNode,
    Project,
    Relation,
)
from src.db.schemas import (
    EntityCreate,
    EpisodicBulkCreate,
    EpisodicItemCreate,
    GraphCreate,
    OntologyCreate,
    ProjectCreate,
    ProjectResponse,
    RelationCreate,
)
from src.db.session import QDRANT_API_KEY, QDRANT_URL, get_db, get_qdrant
from src.server.admin import get_api_key
from src.server.security import hash_key

router = APIRouter(prefix="/v1", tags=["v1"])

# --- Project API ---


@router.post("/projects", response_model=ProjectResponse)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(name=data.name)
    db.add(project)
    db.flush()

    if data.api_key_name:
        plain_key = f"sk-{uuid.uuid4()}"
        hashed = hash_key(plain_key)
        prefix = plain_key[:12]
        ak = ApiKey(
            key=hashed, prefix=prefix, name=data.api_key_name, project_id=project.id
        )
        db.add(ak)

    db.commit()
    db.refresh(project)
    return project


@router.get("/projects", response_model=List[ProjectResponse])
def get_projects(limit: int = 100, db: Session = Depends(get_db)):
    stmt = select(Project).limit(limit)
    return db.execute(stmt).scalars().all()


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    qdrant: QdrantClient = Depends(get_qdrant),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

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
                                match=models.MatchValue(value=str(project_id)),
                            )
                        ]
                    ),
                )
            except Exception:
                pass
    except Exception as e:
        import logging

        logging.getLogger("v1_api").warning(
            f"Failed to delete project vectors from Qdrant: {e}"
        )

    # 2. Delete from DB (cascades to all other child tables)
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
    db: Session = Depends(get_db),
):
    stmt = select(EpisodicItem)

    if project_id:
        if isinstance(project_id, list):
            stmt = stmt.where(EpisodicItem.project_id.in_(project_id))
        else:
            stmt = stmt.where(EpisodicItem.project_id == project_id)

    if api_key_name:
        # Resolve project IDs associated with this key name
        project_ids = (
            db.execute(select(ApiKey.project_id).where(ApiKey.name == api_key_name))
            .scalars()
            .all()
        )
        if project_ids:
            stmt = stmt.where(EpisodicItem.project_id.in_(project_ids))
        else:
            return []  # No projects found for this key name

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
            "metadata": i.metadata_,
        }
        for i in items
    ]


@router.post("/episodic")
async def create_episodic_item(
    data: EpisodicItemCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    qdrant: QdrantClient = Depends(get_qdrant),
    api_key: ApiKey = Depends(get_api_key),
):
    # Enforce API Key Scoping / Tenanting
    data.project_id = str(api_key.project_id)

    ingress = IngressAgent(db, qdrant)
    new_item = ingress.process_memory(data)

    # Schedule condensation in background
    background_tasks.add_task(_condense_project_background, api_key.project_id)

    return {"id": str(new_item.id), "status": "stored"}


@router.post("/episodic/bulk")
async def bulk_ingest(data: EpisodicBulkCreate, background_tasks: BackgroundTasks):
    """
    Ingest many events at once (simulation rounds produce batches).
    When wait=true, block until store + condensation completes (benchmark path).
    """
    if data.wait:
        await run_bulk_ingest(data)
        return {"status": "complete", "count": len(data.episodes)}

    background_tasks.add_task(run_bulk_ingest, data)
    return {"status": "queued", "count": len(data.episodes)}


async def run_bulk_ingest(data: EpisodicBulkCreate):
    from qdrant_client import QdrantClient

    from src.agents.ingress import IngressAgent
    from src.db.session import SessionLocal

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
        response = {"id": str(project.id), "name": project.name, "status": "existing"}
        if data.api_key_name:
            ak = (
                db.query(ApiKey)
                .filter(
                    ApiKey.name == data.api_key_name, ApiKey.project_id == project.id
                )
                .first()
            )
            if ak:
                response["api_key"] = (
                    ak.prefix + "..."
                    if ak.prefix
                    else (
                        ak.key[:12] + "..." if ak.key and len(ak.key) > 12 else "sk-..."
                    )
                )
        return response

    # Otherwise create new project
    project = Project(name=name)
    db.add(project)
    db.flush()

    plain_key = None
    if data.api_key_name:
        plain_key = f"sk-{uuid.uuid4()}"
        hashed = hash_key(plain_key)
        prefix = plain_key[:12]
        ak = ApiKey(
            key=hashed, prefix=prefix, name=data.api_key_name, project_id=project.id
        )
        db.add(ak)

    db.commit()
    db.refresh(project)
    response = {"id": str(project.id), "name": project.name, "status": "created"}
    if data.api_key_name and plain_key:
        response["api_key"] = plain_key
    return response


async def _condense_project_background(project_id: uuid.UUID) -> None:
    """
    Own DB session after the HTTP request ends. Avoids using the request-scoped
    Session in BackgroundTasks (undefined lifecycle vs pool checkout).
    """
    from src.db.session import SessionLocal
    from src.engine.condenser import Condenser

    db = SessionLocal()
    try:
        stmt = select(EpisodicItem).where(EpisodicItem.project_id == project_id)
        items = db.execute(stmt).scalars().all()
        if not items:
            return
        condenser = Condenser(db)
        await condenser.distill(project_id, items)
    finally:
        db.close()


@router.post("/projects/{project_id}/condense")
async def trigger_condensation(
    project_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """
    Trigger the distillation process for all episodic items in this project.
    Now supports both single UUID and JSON list of UUIDs (to fix 422 errors from scripts).
    """
    import json

    # 1. Resolve project_ids
    project_ids = []
    try:
        # Check if it's a bracketed list string like ['uuid1', 'uuid2']
        if project_id.startswith("["):
            # Handle both JSON and Python repr (common in some scripts)
            cleaned = project_id.replace("'", '"')
            pids = json.loads(cleaned)
            if isinstance(pids, list):
                project_ids = [uuid.UUID(str(p)) for p in pids]
        else:
            project_ids = [uuid.UUID(project_id)]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid project_id format: {e}")

    results = []
    for pid in project_ids:
        stmt = select(EpisodicItem).where(EpisodicItem.project_id == pid)
        items = db.execute(stmt).scalars().all()

        if not items:
            results.append(
                {
                    "project_id": str(pid),
                    "status": "skipped",
                    "message": "No items to condense",
                }
            )
            continue

        background_tasks.add_task(_condense_project_background, pid)
        results.append(
            {"project_id": str(pid), "status": "started", "items_count": len(items)}
        )

    return {"status": "processed", "results": results}


@router.post("/graph/entities")
def create_entity(data: EntityCreate, db: Session = Depends(get_db)):
    entity = Entity(
        project_id=data.project_id,
        canonical_name=data.name,
        type=data.type,
        aliases=data.aliases or [],
        confidence=data.confidence or 1.0,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return {"id": str(entity.id), "name": entity.canonical_name, "type": entity.type}


@router.get("/graph/entities")
def get_entities(
    project_id: Optional[List[uuid.UUID]] = Query(None),
    type: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
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
            "confidence": e.confidence,
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
        confidence=data.confidence or 1.0,
    )
    db.add(relation)
    db.commit()
    db.refresh(relation)
    return {"id": str(relation.id)}


@router.get("/graph/relations")
def get_relations(
    project_id: Optional[List[uuid.UUID]] = Query(None),
    entity_id: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    stmt = select(Relation)
    if project_id:
        if isinstance(project_id, list):
            stmt = stmt.where(Relation.project_id.in_(project_id))
        else:
            stmt = stmt.where(Relation.project_id == project_id)
    if entity_id:
        # Search for relations where entity is either source or target
        stmt = stmt.where(
            or_(Relation.from_id == entity_id, Relation.to_id == entity_id)
        )

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
            "provenance": r.provenance,
        }
        for r in relations
    ]


@router.post("/projects/{project_id}/ontology")
def update_ontology(
    project_id: uuid.UUID, data: OntologyCreate, db: Session = Depends(get_db)
):
    """
    Update or create multiple ontology nodes for a specific project.
    """
    for label in data.entity_types:
        # Check if exists
        exists = (
            db.query(OntologyNode)
            .filter(
                OntologyNode.project_id == project_id,
                OntologyNode.label == label,
                OntologyNode.node_type == "entity_type",
            )
            .first()
        )
        if not exists:
            node = OntologyNode(
                project_id=project_id,
                label=label,
                node_type="entity_type",
                confidence=1.0,
            )
            db.add(node)

    for label in data.edge_types:
        exists = (
            db.query(OntologyNode)
            .filter(
                OntologyNode.project_id == project_id,
                OntologyNode.label == label,
                OntologyNode.node_type == "edge_type",
            )
            .first()
        )
        if not exists:
            node = OntologyNode(
                project_id=project_id,
                label=label,
                node_type="edge_type",
                confidence=1.0,
            )
            db.add(node)

    db.commit()
    return {"status": "ok", "project_id": str(project_id)}


@router.get("/projects/{project_id}/ontology")
def get_ontology(project_id: uuid.UUID, db: Session = Depends(get_db)):
    stmt = select(OntologyNode).where(OntologyNode.project_id == project_id)
    nodes = db.execute(stmt).scalars().all()

    entity_types = [n.label for n in nodes if n.node_type == "entity_type"]
    edge_types = [n.label for n in nodes if n.node_type == "edge_type"]

    return {
        "project_id": str(project_id),
        "entity_types": entity_types,
        "edge_types": edge_types,
    }


@router.get("/projects/{project_id}/graph/analytics")
def get_graph_analytics(project_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Compute PageRank centrality, communities, and bottlenecks for a project.
    """
    from src.engine.analytics import GraphAnalyst

    analyst = GraphAnalyst(db, project_id)

    return {
        "project_id": str(project_id),
        "centrality": analyst.get_centrality()[:30],  # Top 30 for UI/Report
        "communities": analyst.get_communities(),
        "bottlenecks": analyst.get_bottlenecks(),
    }


@router.get("/graph/assertions")
def get_assertions(
    project_id: Optional[List[uuid.UUID]] = Query(None),
    subject: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
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
            stmt = stmt.where(
                or_(
                    Assertion.subject_entity_id == sid,
                    Assertion.object_entity_id == sid,
                )
            )
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
            "provenance": a.provenance,
        }
        for a in assertions
    ]


# --- Export API ---


@router.get("/export/jsonl")
def export_jsonl(project_id: str, db: Session = Depends(get_db)):
    # Streaming response would be better for large datasets,
    # but for MVP returning a line-delimited string or list

    # 1. Fetch all items
    items = (
        db.execute(select(EpisodicItem).where(EpisodicItem.project_id == project_id))
        .scalars()
        .all()
    )

    # 2. Fetch all assertions
    assertions = (
        db.execute(select(Assertion).where(Assertion.project_id == project_id))
        .scalars()
        .all()
    )

    import json

    lines = []

    for i in items:
        lines.append(
            json.dumps(
                {
                    "type": "episodic_item",
                    "id": str(i.id),
                    "text": i.text,
                    "source": i.source,
                    "created_at": i.created_at.isoformat(),
                }
            )
        )

    for a in assertions:
        lines.append(
            json.dumps(
                {
                    "type": "assertion",
                    "id": str(a.id),
                    "statement": f"{a.subject_text} {a.predicate} {a.object_text}",
                    "confidence": a.confidence,
                    "provenance": a.provenance,
                }
            )
        )

    from fastapi.responses import Response

    return Response(content="\n".join(lines), media_type="application/x-jsonlines")
