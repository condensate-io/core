import os
import json
from typing import List, AsyncGenerator
from openai import AsyncOpenAI
from tenacity import retry, wait_exponential, stop_after_attempt

from src.db.models import EpisodicItem
from src.llm.schemas import ExtractionBundle, ExtractedEntity, ExtractedAssertion, ExtractedEvent, ExtractedPolicy

from src.llm.client import LLMClient

# Constants
MODEL_NAME = os.getenv("LLM_MODEL", "phi3") # Default to phi3 for local

llm_client = LLMClient()

# ...
llm_client = LLMClient()

EXTRACTION_PROMPT = """
You are a Cognitive Memory Condenser.
Your job is to read a raw episodic memory item and extract structured knowledge from it.
Output MUST be a valid JSON object matching the following schema.

Schema Definition:
- entities: List of canonical entities (People, Organizations, Systems, Concepts) mentioned.
- assertions: List of factual claims. Subject/Object should be entity references or literals.
- events: Significant occurrences (meetings, decisions, incidents) if any.
- policies: Operational rules or constraints to remember (e.g. "Do not use library X").

Rules:
1. Be conservative. Only extract what is explicitly stated or strongly implied.
2. Canonicalize names where possible (e.g., "Bob" -> "Bob Smith", "the db" -> "Primary Database").
3. Polarity: 1 for affirmative ("is"), -1 for negative ("is not").
4. Confidence: 0.0 to 1.0 based on how clear the text is.

Input Text:
{text}

Input Metadata:
{metadata}

Respond ONLY with the JSON.
"""

class MemoryExtractor:
    def __init__(self, model: str = MODEL_NAME):
        self.model = model

    async def extract(self, items: List[EpisodicItem]) -> List[ExtractionBundle]:
        """
        Process a batch of EpisodicItems and return an ExtractionBundle for each.
        """
        results = []
        for item in items:
            # Prepare Prompt
            prompt = EXTRACTION_PROMPT.format(
                text=item.text,
                metadata=json.dumps(item.metadata_ or {}, default=str)
            )

            content = await llm_client.generate(
                prompt=prompt,
                system_prompt="You are a precise knowledge extraction engine. Output strict JSON."
            )
            
            if not content or not content.strip():
                results.append(ExtractionBundle())
                continue
            
            try:
                # Basic cleanup in case of leading/trailing junk
                cleaned_content = content.strip()
                if cleaned_content.startswith("```json"):
                    cleaned_content = cleaned_content.removeprefix("```json").removesuffix("```").strip()
                elif cleaned_content.startswith("```"):
                     cleaned_content = cleaned_content.removeprefix("```").removesuffix("```").strip()

                data = json.loads(cleaned_content)
                # Transform raw dict to Pydantic models with correct evidence
                bundle = ExtractionBundle(
                    entities=[ExtractedEntity(**e) for e in data.get("entities", [])],
                    assertions=[self._enrich_assertion(a, item.id) for a in data.get("assertions", [])],
                    events=[self._enrich_event(e, item.id) for e in data.get("events", [])],
                    policies=[self._enrich_policy(p, item.id) for p in data.get("policies", [])]
                )
                results.append(bundle)
            except Exception as e:
                print(f"Error parsing JSON for item {item.id}: {e}")
                results.append(ExtractionBundle())

        return results

    def _enrich_assertion(self, raw: dict, item_id: str):
        # Add source evidence if missing (LLM might not populate it strictly)
        if "evidence" not in raw or not raw["evidence"]:
            raw["evidence"] = [{"episodic_id": str(item_id), "quote": "Derived from item"}]
        return ExtractedAssertion(**raw)

    def _enrich_event(self, raw: dict, item_id: str):
        if "evidence" not in raw or not raw["evidence"]:
            raw["evidence"] = [{"episodic_id": str(item_id), "quote": "Derived from item"}]
        return ExtractedEvent(**raw)

    def _enrich_policy(self, raw: dict, item_id: str):
        if "evidence" not in raw or not raw["evidence"]:
            raw["evidence"] = [{"episodic_id": str(item_id), "quote": "Derived from item"}]
        return ExtractedPolicy(**raw)
