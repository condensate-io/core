import json
import logging
from typing import List, Dict, Any, Optional
from src.llm.client import LLMClient

logger = logging.getLogger(__name__)

RERANK_PROMPT = """
You are a Context Reranker. Your job is to select the most relevant pieces of information for the given query.
Score each item from 0 to 10 based on its relevance to the query.

Query: {query}

Items to Rank:
{items}

Output MUST be a JSON object with "ranked_indices" being a list of indices sorted by relevance (descending).
{{
    "ranked_indices": [2, 0, 1, ...]
}}
"""

class LocalReranker:
    def __init__(self, llm_config: Optional[Dict[str, str]] = None):
        self.llm_client = LLMClient()
        self.llm_config = llm_config

    async def rerank(self, query: str, documents: List[str], top_n: int = 10) -> List[str]:
        """
        Rerank a list of documents based on a query using the LLM.
        """
        if not documents:
            return []
        
        if len(documents) == 1:
            return documents

        # Prepare items with indices
        items_text = ""
        for i, doc in enumerate(documents):
            items_text += f"[{i}] {doc}\n\n"

        prompt = RERANK_PROMPT.format(query=query, items=items_text)
        
        try:
            content = await self.llm_client.generate(
                prompt=prompt,
                system_prompt="You are a precise reranking engine. Output JSON only."
            )
            
            # Clean JSON
            cleaned = content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned.removeprefix("```json").removesuffix("```").strip()
            
            data = json.loads(cleaned)
            indices = data.get("ranked_indices", [])
            
            ranked_docs = []
            for idx in indices:
                if 0 <= idx < len(documents):
                    ranked_docs.append(documents[idx])
            
            # Add any missing docs at the end JUST in case
            seen = set(ranked_docs)
            for doc in documents:
                if doc not in seen:
                    ranked_docs.append(doc)
                    
            return ranked_docs[:top_n]
            
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            # Fallback to original order
            return documents[:top_n]
