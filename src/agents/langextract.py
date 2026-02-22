import logging
import json
import uuid
from typing import List, Dict, Any, Optional
from src.llm.client import LLMClient
from src.db.models import Assertion, EpisodicItem
from src.llm.schemas import ExtractionBundle

logger = logging.getLogger("LangExtract")

class LangExtract:
    """
    Adapter for extracting structured insights from text using LLMs.
    This replaces the raw LLM calls in the Condensation Agent with a more formalized pipeline.
    """
    def __init__(self):
        self.llm = LLMClient()
        
    async def extract(self, items: List[EpisodicItem]) -> List[ExtractionBundle]:
        """
        Implements the MemoryExtractor interface.
        Extracts structured knowledge (Assertions, Policies) from a batch of items.
        """
        from src.llm.schemas import ExtractionBundle, ExtractedAssertion, ExtractedPolicy

        results = []
        for item in items:
            bundle = ExtractionBundle()
            
            # 1. Extract "Learnings" -> Policies or General Assertions
            learnings = await self.extract_learnings(item.text)
            for l in learnings:
                # Map "learning" to Policy if it looks like a rule, else Assertion
                # For simplicity in this adapter, we might map strictly to Policies if confidence is high
                # or treat them as Assertions about "User Preference".
                
                # Heuristic: If statement contains "must", "should", "always", "never", treat as Policy
                statement = l.get("statement", "")
                if any(k in statement.lower() for k in ["must", "should", "always", "never", "do not"]):
                    bundle.policies.append(ExtractedPolicy(
                        trigger="general_context", # Inferred
                        rule=statement,
                        priority=l.get("confidence", 0.5),
                        evidence=[{"episodic_id": str(item.id), "quote": l.get("rich_description")}]
                    ))
                else:
                    # Generic Assertion
                    bundle.assertions.append(ExtractedAssertion(
                        subject="User",
                        predicate="has_preference_or_fact",
                        object=statement,
                        confidence=l.get("confidence", 0.5),
                        evidence=[{"episodic_id": str(item.id), "quote": l.get("rich_description")}]
                    ))

            # 2. Extract Triplets -> Assertions
            triplets = await self.extract_triplets(item.text)
            for t in triplets:
                bundle.assertions.append(ExtractedAssertion(
                    subject=t.get("subject"),
                    predicate=t.get("predicate"),
                    object=t.get("object"),
                    confidence=0.8, # Default for direct extraction
                    evidence=[{"episodic_id": str(item.id), "quote": "Triples extraction"}]
                ))
            
            results.append(bundle)
            
        return results

    async def extract_learnings(self, text_corpus: str) -> List[Dict[str, Any]]:
        """
        Extracts learnings from a text corpus.
        Returns a list of dictionaries with keys: 'statement', 'rich_description', 'confidence', 'evidence_indices'.
        """
        prompt = f"""
        Analyze the following text and extract 'Learnings'.
        A Learning is a recurring pattern, a user preference, or a factual constraint.
        
        Output valid JSON only:
        [
            {{
                "statement": "Concise single sentence statement",
                "rich_description": "Detailed explanation of the learning...",
                "confidence": 0.0 to 1.0 (float),
                "evidence_indices": [0, 2] // Indices of the source inputs that support this
            }}
        ]
        
        Corpus:
        {text_corpus}
        """
        
        try:
            response = await self.llm.generate(prompt, system_prompt="You are LangExtract, an advanced knowledge extraction engine.")
            # Clean response
            response = response.replace("```json", "").replace("```", "").strip()
            return json.loads(response)
        except Exception as e:
            logger.error(f"LangExtract failed: {e}")
            return []

    async def extract_triplets(self, text: str) -> List[Dict[str, str]]:
        """
        Extracts Subject-Predicate-Object triplets for Ontology Construction.
        """
        prompt = f"""
        Extract knowledge graph triplets from the text.
        Output JSON: [{{"subject": "...", "predicate": "...", "object": "..."}}]
        
        Text: {text}
        """
        try:
            response = await self.llm.generate(prompt)
            response = response.replace("```json", "").replace("```", "").strip()
            return json.loads(response)
        except Exception:
            return []
