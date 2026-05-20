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
- entities: List of objects with [name, type, aliases, confidence]
- assertions: List of factual claims with:
    - subject: object ({{ "type": "entity", "name": "name" }} or {{ "type": "literal", "value": "value" }})
    - predicate: string (the relationship verb)
    - object: object ({{ "type": "entity", "name": "name" }} or {{ "type": "literal", "value": "value" }})
    - polarity: integer (1 for affirmative, -1 for negative)
    - confidence: float (0.0 to 1.0)
- events: Significant occurrences [type, summary, confidence]
- policies: Operational rules [trigger, rule, priority, scope, confidence]

Onboard Precision Guidelines (Determinism):
1. Use high-signal verbs for predicates whenever possible: 
   - Actions: executed, triggered, stabilized, bought, sold, implemented, failed, succeeded, notified.
   - States: owns, belongs_to, part_of, located_at, prefers, knows, depends_on, manages.
2. Be conservative. If an action is not explicitly stated, do not hallucinate a relationship.
3. If the input contains strategic orders or market anomalies (e.g. "sudden price spike", "massive buy"), ensure these are captured as assertions or events.
4. Respond ONLY with raw JSON.

Input Text:
{text}

Input Metadata:
{metadata}
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

                # Robust JSON parsing
                try:
                    data = json.loads(cleaned_content)
                except json.JSONDecodeError as jde:
                    # Try advanced cleanup
                    print(f"[MemoryExtractor] Initial JSON parse failed: {jde}. Attempting repair...")
                    repaired = self._cleanup_json(cleaned_content)
                    data = json.loads(repaired)

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

    def _cleanup_json(self, raw_str: str) -> str:
        """Fixes common LLM JSON syntax errors."""
        import re
        
        # 1. Replace single quotes around property names with double quotes
        # Note: This is a bit unsafe but often works for simple objects
        fixed = re.sub(r"'(\w+)':", r'"\1":', raw_str)
        
        # 2. Remove trailing commas in objects and arrays
        fixed = re.sub(r",\s*([\}\]])", r"\1", fixed)
        
        # 3. Ensure balanced braces/brackets (simple append)
        if fixed.count("{") > fixed.count("}"):
            fixed += "}" * (fixed.count("{") - fixed.count("}"))
        if fixed.count("[") > fixed.count("]"):
            fixed += "]" * (fixed.count("[") - fixed.count("]"))
            
        return fixed

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
