import os
import json
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from qdrant_client import QdrantClient
from sqlalchemy.orm import Session
from sqlalchemy import select, text
from src.db.models import Assertion, Entity

# Constants
MODEL_NAME = os.getenv("LLM_MODEL", "gpt-4-turbo")
BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
API_KEY = os.getenv("LLM_API_KEY", "sk-placeholder")

client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)

ROUTER_PROMPT = """
You are a Memory Router. Your job is to classify the user's query and decide the best retrieval strategy.

Query: {query}

Strategies:
1. "recall": Simple factual lookup. Use Vector Search. (e.g. "What did Bob say about the DB?")
2. "research": Complex multi-hop reasoning. Use Graph Traversal + Vector. (e.g. "How has the architecture evolved?")
3. "meta": Questions about the system itself. (e.g. "How many memories do I have?")

Output JSON:
{{
    "strategy": "recall" | "research" | "meta",
    "keywords": ["list", "of", "search", "terms"]
}}
"""

class MemoryRouter:
    def __init__(self, db: Session, qdrant: QdrantClient):
        self.db = db
        self.qdrant = qdrant

    async def route_and_retrieve(self, project_id: str, query: str, skip_llm: bool = False, llm_config: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Main entry point: Classification -> Retrieval -> Synthesis
        """
        # 1. Classify Intent
        # If skip_llm is True, we might still need classification, or we could force "recall" if we want to be purely deterministic.
        # But let's keep classification to show the "Traffic Control" decision.
        plan = await self._classify(query, llm_config)
        strategy = plan.get("strategy", "recall")
        keywords = plan.get("keywords", [])

        context = ""
        sources = []

        if strategy == "recall":
            context, sources = await self._vector_search(project_id, query)
        
        elif strategy == "research":
            # Graph + Vector
            graph_context, graph_sources = self._graph_traversal(project_id, keywords)
            vec_context, vec_sources = await self._vector_search(project_id, query)
            
            context = f"GRAPH KNOWLEDGE:\n{graph_context}\n\nVECTOR MEMORY:\n{vec_context}"
            sources = graph_sources + vec_sources
            
        elif strategy == "meta":
            # Just simple stats for now
            context = "System functionality query."
            sources = []

        # 2. Synthesize Answer (Brief)
        if skip_llm:
            answer = f"**TRAFFIC CONTROL: LLM SKIPPED**\n\nStrategy: {strategy}\n\nContext Retrieved:\n{context}"
        else:
            answer = await self._synthesize(query, context, llm_config)

        # 3. Cognitive Dynamics: Hebbian Learning
        # Strengthen connections between retrieved sources
        if sources:
            try:
                # Convert 'source' strings (UUIDs) back to UUID objects
                import uuid
                source_ids = []
                for s in sources:
                    try:
                        source_ids.append(uuid.UUID(s))
                    except:
                        pass
                
                if source_ids:
                    from src.engine.cognitive import CognitiveService
                    cog = CognitiveService(self.db)
                    cog.hebbian_update(source_ids)
            except Exception as e:
                print(f"Hebbian update failed: {e}")

        return {
            "answer": answer,
            "sources": sources,
            "strategy": strategy
        }

    async def _classify(self, query: str, llm_config: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        use_client = client
        model = MODEL_NAME
        
        if llm_config:
            from openai import AsyncOpenAI
            use_client = AsyncOpenAI(
                api_key=llm_config.get("api_key", API_KEY),
                base_url=llm_config.get("base_url", BASE_URL)
            )
            model = llm_config.get("model", MODEL_NAME)

        try:
            response = await use_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": ROUTER_PROMPT.format(query=query)}],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            return json.loads(response.choices[0].message.content)
        except:
            return {"strategy": "recall", "keywords": []}

    async def _vector_search(self, project_id: str, query: str):
        """
        Real vector search: embed the query with fastembed, then search Qdrant
        for the top-10 nearest episodic items in this project.
        """
        if self.qdrant is None:
            return "Vector search unavailable (no Qdrant client).", []

        try:
            from fastembed import TextEmbedding
            embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
            query_vectors = list(embedding_model.embed([query]))
            if not query_vectors:
                return "Could not embed query.", []
            query_vector = query_vectors[0].tolist()
        except Exception as e:
            return f"Embedding error: {e}", []

        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            search_filter = Filter(
                must=[FieldCondition(key="project_id", match=MatchValue(value=project_id))]
            )
            results = self.qdrant.search(
                collection_name="episodic_chunks",
                query_vector=query_vector,
                query_filter=search_filter,
                limit=10,
                with_payload=True
            )
        except Exception as e:
            # Collection may not exist yet or Qdrant unavailable
            return f"Qdrant search error: {e}", []

        if not results:
            return "No relevant memories found.", []

        context_parts = []
        source_ids = []
        for hit in results:
            payload = hit.payload or {}
            text = payload.get("text", "")
            item_id = payload.get("item_id", str(hit.id))
            score = round(hit.score, 3)
            context_parts.append(f"[score={score}] {text}")
            source_ids.append(item_id)

        return "\n\n".join(context_parts), source_ids


    def _graph_traversal(self, project_id: str, keywords: List[str]):
        """
        Research Strategy: Find entities -> Spreading Activation -> Get Assertions
        """
        if not keywords:
            return "", []

        # 1. Find Seed Entities
        entities = self.db.execute(
            select(Entity).where(
                Entity.project_id == project_id,
                Entity.canonical_name.in_([k.lower() for k in keywords]) 
            )
        ).scalars().all()
        
        if not entities:
            return "No matching entities found in graph.", []

        seed_ids = [e.id for e in entities]
        
        # 2. Spreading Activation
        from src.engine.cognitive import CognitiveService
        cog = CognitiveService(self.db)
        activated_ids = cog.spreading_activation(seed_ids, steps=2)
        
        # 3. Retrieve Assertions for Activated Entities (only approved/active)
        assertions = self.db.execute(
            select(Assertion).where(
                Assertion.project_id == project_id,
                Assertion.status.in_(['approved', 'active']),
                (Assertion.subject_entity_id.in_(activated_ids)) | (Assertion.object_entity_id.in_(activated_ids))
            ).limit(20) # Cap context
            .order_by(Assertion.strength.desc()) # Prioritize strong memories (LTP)
        ).scalars().all()
        
        context = "\n".join([f"- {a.subject_text} {a.predicate} {a.object_text} (conf: {a.confidence}, str: {a.strength})" for a in assertions])
        sources = [str(a.id) for a in assertions]
        
        return context, sources

    async def _synthesize(self, query: str, context: str, llm_config: Optional[Dict[str, str]] = None) -> str:
        use_client = client
        model = MODEL_NAME
        
        if llm_config:
            from openai import AsyncOpenAI
            use_client = AsyncOpenAI(
                api_key=llm_config.get("api_key", API_KEY),
                base_url=llm_config.get("base_url", BASE_URL)
            )
            model = llm_config.get("model", MODEL_NAME)

        sys_prompt = "You are a helpful assistant. Answer the user query based ONLY on the provided context."
        user_msg = f"Context:\n{context}\n\nQuery: {query}"
        
        response = await use_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.0
        )
        return response.choices[0].message.content
