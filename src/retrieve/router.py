import os
import json
import logging
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from qdrant_client import QdrantClient
from sqlalchemy.orm import Session
from sqlalchemy import select, text
from src.db.models import Assertion, Entity

# Constants
from src.llm.client import LLMClient

logger = logging.getLogger(__name__)

def get_current_client(config: Optional[Dict[str, str]] = None):
    """Dynamically resolves the LLM settings from the config file if not provided explicitly."""
    if not config:
        config = LLMClient.get_active_config()
    
    return AsyncOpenAI(
        api_key=config.get("apiKey", config.get("api_key", "sk-placeholder")),
        base_url=config.get("baseUrl", config.get("base_url", "https://api.openai.com/v1"))
    ), config.get("model", "gpt-4-turbo")

ROUTER_PROMPT = """
You are a Memory Router. Your job is to classify the user's query and decide the best retrieval strategy.

Query: {query}

Strategies:
1. "recall": Simple factual lookup. Use Vector Search. (e.g. "What did Bob say about the DB?")
2. "research": Complex multi-hop reasoning. Use Graph Traversal + Vector. (e.g. "How has the architecture evolved?")
3. "meta": Questions about the system itself. (e.g. "How many memories do I have?")

Complexity Scoring:
- Score 1: Simple retrieval.
- Score 2: Default research.
- Score 3: Deep investigation. (Boost to 3 if user uses systemic keywords like "cascade", "impact", "origin", "influence", or "root cause").

Output JSON:
{{
    "strategy": "recall" | "research" | "meta",
    "keywords": ["list", "of", "search", "terms"],
    "complexity": 1 | 2 | 3
}}
"""

class MemoryRouter:
    def __init__(self, db: Session, qdrant: QdrantClient):
        self.db = db
        self.qdrant = qdrant

    async def route_and_retrieve(self, project_id: Any, query: str, skip_llm: bool = False, llm_config: Optional[Dict[str, str]] = None, current_step: Optional[int] = None) -> Dict[str, Any]:
        """
        Main entry point: Classification -> Retrieval -> Synthesis
        """
        # 1. Classify Intent
        # If skip_llm is True, we might still need classification, or we could force "recall" if we want to be purely deterministic.
        # But let's keep classification to show the "Traffic Control" decision.
        plan = await self._classify(query, llm_config)
        strategy = plan.get("strategy", "recall")
        keywords = plan.get("keywords", [])
        complexity = int(plan.get("complexity", 2))

        context_items: List[str] = []
        sources = []
        confidence_score = 0.0

        if strategy == "recall":
            vec_items, vec_sources, max_score = await self._vector_search(project_id, query, current_step=current_step)
            context_items.extend(vec_items)
            sources = vec_sources
            confidence_score = max_score
        
        elif strategy == "research":
            # Graph + Vector
            # Adjust depth/decay based on complexity
            steps = 1 if complexity == 1 else (3 if complexity == 3 else 2)
            decay = 0.7 if complexity == 1 else (0.3 if complexity == 3 else 0.5)
            
            graph_items, graph_sources, graph_conf = self._graph_traversal(project_id, keywords, steps=steps, decay=decay)
            vec_items, vec_sources, vec_conf = await self._vector_search(project_id, query, current_step=current_step)
            
            context_items = graph_items + vec_items
            sources = graph_sources + vec_sources
            confidence_score = max(graph_conf, vec_conf)
            
        elif strategy == "meta":
            # Just simple stats for now
            context_items = ["System functionality query."]
            sources = []
            confidence_score = 1.0

        # --- Reranking Layer ---
        from src.retrieve.reranker import LocalReranker
        reranker = LocalReranker(llm_config=llm_config)
        
        # Reranked top-N for the final context window
        final_items = await reranker.rerank(query, context_items, top_n=12)
        context = "\n\n".join(final_items)
        
        THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.8"))

        # 2. Synthesize Answer (Brief)
        if skip_llm or confidence_score >= THRESHOLD:
            if not skip_llm:
                answer = f"**TRAFFIC CONTROL: LLM SKIPPED (Confidence: {confidence_score:.2f} >= {THRESHOLD})**\n\nStrategy: {strategy}\n\nContext Retrieved:\n{context}"
            else:
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

                    # --- Synapse Engine Strengthening ---
                    try:
                        from src.synapses.config import synapse_config
                        if synapse_config.ENABLED:
                            from src.synapses.engine import SynapseEngine
                            syn_engine = SynapseEngine(self.db)
                            syn_engine.strengthen_on_retrieval(source_ids, query)
                    except Exception as se_exc:
                        logger.warning("Synapse strengthening failed: %s", se_exc)
            except Exception as e:
                logger.warning("Hebbian update failed: %s", e)

        return {
            "answer": answer,
            "sources": sources,
            "strategy": strategy
        }

    async def _classify(self, query: str, llm_config: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Classify the user intent into recall, research, or meta strategies using the active LLM."""
        try:
            use_client, model = get_current_client(llm_config)
            
            response = await use_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": ROUTER_PROMPT.format(query=query)}],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            # Fallback to simple recall if LLM fails or is unconfigured
            logger.warning("Router classification failed: %s", e)
            return {"strategy": "recall", "keywords": []}

    async def _vector_search(self, project_id: Any, query: str, current_step: Optional[int] = None):
        """
        Real vector search: embed the query with fastembed, then search Qdrant
        for the top-10 nearest episodic items in this project.
        """
        if self.qdrant is None:
            return [], [], 0.0

        try:
            from fastembed import TextEmbedding
            # Use GPU providers if available
            try:
                import onnxruntime as ort
                available = ort.get_available_providers()
                providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if "CUDAExecutionProvider" in available else ["CPUExecutionProvider"]
            except ImportError:
                providers = ["CPUExecutionProvider"]
            embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5", providers=providers)
            query_vectors = list(embedding_model.embed([query]))
            if not query_vectors:
                return [], [], 0.0
            query_vector = query_vectors[0].tolist()
        except Exception as e:
            return [], [], 0.0

        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny
            if isinstance(project_id, list):
                search_filter = Filter(
                    must=[FieldCondition(key="project_id", match=MatchAny(any=project_id))]
                )
            else:
                search_filter = Filter(
                    must=[FieldCondition(key="project_id", match=MatchValue(value=project_id))]
                )
            results = self.qdrant.search(
                collection_name="episodic_chunks",
                query_vector=query_vector,
                query_filter=search_filter,
                limit=30 if current_step is not None else 10,
                with_payload=True
            )
        except Exception as e:
            # Collection may not exist yet or Qdrant unavailable
            return [], [], 0.0

        if current_step is not None:
            import math
            decay_rate = 0.05 # Exponential decay factor for simulation steps
            for hit in results:
                payload = hit.payload or {}
                # Get simulation_step from metadata
                meta = payload.get("metadata", {})
                memory_step = meta.get("simulation_step")
                
                if memory_step is not None:
                    # score = vector_similarity * exp(-decay_rate * (current_step - memory_step))
                    try:
                        time_diff = max(0, current_step - int(memory_step))
                        decay_factor = math.exp(-decay_rate * time_diff)
                        hit.score = hit.score * decay_factor
                    except:
                        pass
            
            # Re-sort by updated score and truncate
            results.sort(key=lambda x: x.score, reverse=True)
            results = results[:10]

        if not results:
            return "No relevant memories found.", [], 0.0

        context_parts = []
        source_ids = []
        max_score = 0.0
        for hit in results:
            payload = hit.payload or {}
            text = payload.get("text", "")
            item_id = payload.get("item_id", str(hit.id))
            score = round(hit.score, 3)
            max_score = max(max_score, score)
            context_parts.append(f"[score={score}] {text}")
            source_ids.append(item_id)

        return context_parts, source_ids, max_score


    def _graph_traversal(self, project_id: Any, keywords: List[str], steps: int = 2, decay: float = 0.5):
        """
        Research Strategy: Find entities -> Spreading Activation -> Get Assertions
        """
        if not keywords:
            return "", [], 0.0

        # 1. Find Seed Entities
        if isinstance(project_id, list):
            ent_stmt = select(Entity).where(
                Entity.project_id.in_(project_id),
                Entity.canonical_name.in_([k.lower() for k in keywords]) 
            )
        else:
            ent_stmt = select(Entity).where(
                Entity.project_id == project_id,
                Entity.canonical_name.in_([k.lower() for k in keywords]) 
            )
        entities = self.db.execute(ent_stmt).scalars().all()
        
        if not entities:
            return [], [], 0.0

        seed_ids = [e.id for e in entities]
        
        # 2. Spreading Activation
        from src.engine.cognitive import CognitiveService
        cog = CognitiveService(self.db)
        activated_ids = cog.spreading_activation(seed_ids, steps=steps, decay_factor=decay)
        
        # 3. Retrieve Assertions for Activated Entities (only approved/active)
        if isinstance(project_id, list):
            ass_stmt = select(Assertion).where(
                Assertion.project_id.in_(project_id),
                Assertion.status.in_(['approved', 'active']),
                (Assertion.subject_entity_id.in_(activated_ids)) | (Assertion.object_entity_id.in_(activated_ids))
            )
        else:
            ass_stmt = select(Assertion).where(
                Assertion.project_id == project_id,
                Assertion.status.in_(['approved', 'active']),
                (Assertion.subject_entity_id.in_(activated_ids)) | (Assertion.object_entity_id.in_(activated_ids))
            )
            
        assertions = self.db.execute(
            ass_stmt.limit(20) # Cap context
            .order_by(Assertion.strength.desc()) # Prioritize strong memories (LTP)
        ).scalars().all()
        
        context_parts = [f"Assertion: {a.subject_text} {a.predicate} {a.object_text} (conf: {a.confidence}, str: {a.strength})" for a in assertions]
        sources = [str(a.id) for a in assertions]
        
        max_conf = max([a.confidence for a in assertions]) if assertions else 0.0
        
        return context_parts, sources, max_conf

    async def _synthesize(self, query: str, context: str, llm_config: Optional[Dict[str, str]] = None) -> str:
        """Combine context and query into a natural language response using the active LLM."""
        try:
            use_client, model = get_current_client(llm_config)

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
        except Exception as e:
            return f"Answer synthesis failed: {e}. Raw context preserved: {context[:500]}..."
