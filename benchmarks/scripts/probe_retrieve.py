#!/usr/bin/env python3
"""Quick probe: Qdrant points + retrieve for conv-26 project."""
from __future__ import annotations

import os
import sys
import uuid

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

PROJECT_NAME = sys.argv[1] if len(sys.argv) > 1 else "conv-26"
BASE_URL = os.getenv("CONDENSATE_URL", "http://localhost:8000")
ADMIN_KEY = os.getenv("CONDENSATE_API_KEY", "")

pid = str(uuid.uuid5(uuid.NAMESPACE_DNS, PROJECT_NAME))
print(f"project_id={pid}")

client = QdrantClient(host=os.getenv("QDRANT_HOST", "localhost"), port=int(os.getenv("QDRANT_PORT", "6333")))
points, _ = client.scroll(
    collection_name="episodic_chunks",
    scroll_filter=Filter(must=[FieldCondition(key="project_id", match=MatchValue(value=pid))]),
    limit=3,
    with_payload=True,
)
print(f"qdrant_points_sample={len(points)}")
if points:
    print(f"sample_text={points[0].payload.get('text', '')[:160]!r}")

headers = {"Content-Type": "application/json"}
if ADMIN_KEY:
    headers["Authorization"] = f"Bearer {ADMIN_KEY}"

# Create scoped key for project
with httpx.Client(timeout=120.0) as http:
    key_resp = http.post(
        f"{BASE_URL}/api/admin/keys",
        params={"name": f"probe-{PROJECT_NAME}", "project_id": PROJECT_NAME},
        headers=headers,
    )
    key_resp.raise_for_status()
    key_body = key_resp.json()
    scoped = key_body["key"]
    print(f"scoped_project={key_body['project_id']}")

    retrieve_resp = http.post(
        f"{BASE_URL}/api/v1/memory/retrieve",
        json={"query": "When did Caroline go to the LGBTQ support group?"},
        headers={"Authorization": f"Bearer {scoped}", "Content-Type": "application/json"},
    )
    print(f"retrieve_status={retrieve_resp.status_code}")
    data = retrieve_resp.json()
    print(f"strategy={data.get('strategy')}")
    print(f"context_len={len(data.get('context') or '')}")
    print(f"answer_len={len(data.get('answer') or '')}")
    print(f"sources={len(data.get('sources') or [])}")
    ctx = (data.get("context") or "")[:300]
    if ctx:
        print(f"context_preview={ctx!r}")

    # Direct vector search debug
    from src.retrieve.router import MemoryRouter, _get_query_embedding
    from src.db.session import SessionLocal

    query = "When did Caroline go to the LGBTQ support group?"
    try:
        emb = _get_query_embedding()
        vecs = list(emb.embed([query]))
        print(f"embed_ok dim={len(vecs[0]) if vecs else 0}")
        qv = vecs[0].tolist()
        results = client.search(
            collection_name="episodic_chunks",
            query_vector=qv,
            query_filter=Filter(must=[FieldCondition(key="project_id", match=MatchValue(value=pid))]),
            limit=5,
            with_payload=True,
        )
        print(f"legacy_search_hits={len(results)}")
    except Exception as exc:
        print(f"legacy_search_error={exc!r}")
    try:
        resp = client.query_points(
            collection_name="episodic_chunks",
            query=qv,
            query_filter=Filter(must=[FieldCondition(key="project_id", match=MatchValue(value=pid))]),
            limit=5,
            with_payload=True,
        )
        print(f"query_points_hits={len(resp.points)}")
        if resp.points:
            print(f"top_score={resp.points[0].score}")
            print(f"top_text={resp.points[0].payload.get('text','')[:120]!r}")
    except Exception as exc:
        print(f"query_points_error={exc!r}")

    db = SessionLocal()
    try:
        mr = MemoryRouter(db, client)
        import asyncio

        result = asyncio.run(mr.route_and_retrieve(pid, query))
        print(f"router_context_len={len(result.get('context') or '')}")
        print(f"router_sources={len(result.get('sources') or [])}")
    finally:
        db.close()
