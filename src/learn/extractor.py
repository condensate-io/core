import os
import json
import logging
from typing import List, AsyncGenerator, Optional, Any
from openai import AsyncOpenAI
from tenacity import retry, wait_exponential, stop_after_attempt

from src.db.models import EpisodicItem
from src.llm.schemas import ExtractionBundle, ExtractedEntity, ExtractedAssertion, ExtractedEvent, ExtractedPolicy

from src.llm.client import LLMClient

logger = logging.getLogger(__name__)

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
                    logger.warning("Initial JSON parse failed: %s. Attempting repair...", jde)
                    repaired = self._cleanup_json(cleaned_content)
                    data = json.loads(repaired)

                # Transform raw dict to Pydantic models; skip malformed items instead of dropping the bundle
                bundle = ExtractionBundle(
                    entities=self._parse_entities(data.get("entities", []), item.id),
                    assertions=self._parse_assertions(data.get("assertions", []), item.id),
                    events=self._parse_events(data.get("events", []), item.id),
                    policies=self._parse_policies(data.get("policies", []), item.id),
                )
                results.append(bundle)
            except Exception as e:
                logger.error("Error parsing JSON for item %s: %s", item.id, e)
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

    def _parse_entities(self, raw_entities: List[Any], item_id: str) -> List[ExtractedEntity]:
        parsed: List[ExtractedEntity] = []
        for raw in raw_entities:
            if not isinstance(raw, dict):
                continue
            try:
                parsed.append(ExtractedEntity(**raw))
            except Exception as exc:
                logger.warning("Skipping malformed entity for item %s: %s", item_id, exc)
        return parsed

    def _parse_assertions(self, raw_assertions: List[Any], item_id: str) -> List[ExtractedAssertion]:
        parsed: List[ExtractedAssertion] = []
        for raw in raw_assertions:
            assertion = self._enrich_assertion(raw, item_id)
            if assertion is not None:
                parsed.append(assertion)
        return parsed

    def _parse_events(self, raw_events: List[Any], item_id: str) -> List[ExtractedEvent]:
        parsed: List[ExtractedEvent] = []
        for raw in raw_events:
            event = self._enrich_event(raw, item_id)
            if event is not None:
                parsed.append(event)
        return parsed

    def _parse_policies(self, raw_policies: List[Any], item_id: str) -> List[ExtractedPolicy]:
        parsed: List[ExtractedPolicy] = []
        for raw in raw_policies:
            policy = self._enrich_policy(raw, item_id)
            if policy is not None:
                parsed.append(policy)
        return parsed

    def _normalize_assertion_raw(self, data: dict) -> dict:
        if data.get("object") is None:
            for alias in ("obj", "object_ref", "target", "object_value"):
                if data.get(alias) is not None:
                    data["object"] = data[alias]
                    break
        if data.get("object") is None and isinstance(data.get("value"), str):
            data["object"] = {"type": "literal", "value": data["value"]}
        if not data.get("predicate"):
            for alias in ("relation", "relationship", "verb"):
                if data.get(alias):
                    data["predicate"] = str(data[alias])
                    break
        return data

    def _enrich_assertion(self, raw: Any, item_id: str) -> Optional[ExtractedAssertion]:
        if not isinstance(raw, dict):
            return None
        data = self._normalize_assertion_raw(dict(raw))
        if data.get("object") is None or not data.get("predicate"):
            logger.warning(
                "Skipping incomplete assertion for item %s (missing object or predicate): %s",
                item_id,
                {k: data[k] for k in data if k in ("subject", "predicate", "object", "polarity")},
            )
            return None
        if "evidence" not in data or not data["evidence"]:
            data["evidence"] = [{"episodic_id": str(item_id), "quote": "Derived from item"}]
        try:
            return ExtractedAssertion(**data)
        except Exception as exc:
            logger.warning("Skipping malformed assertion for item %s: %s", item_id, exc)
            return None

    def _enrich_event(self, raw: Any, item_id: str) -> Optional[ExtractedEvent]:
        if not isinstance(raw, dict):
            return None
        data = dict(raw)
        if "evidence" not in data or not data["evidence"]:
            data["evidence"] = [{"episodic_id": str(item_id), "quote": "Derived from item"}]
        try:
            return ExtractedEvent(**data)
        except Exception as exc:
            logger.warning("Skipping malformed event for item %s: %s", item_id, exc)
            return None

    def _enrich_policy(self, raw: Any, item_id: str) -> Optional[ExtractedPolicy]:
        if not isinstance(raw, dict):
            return None
        data = dict(raw)
        if "evidence" not in data or not data["evidence"]:
            data["evidence"] = [{"episodic_id": str(item_id), "quote": "Derived from item"}]
        try:
            return ExtractedPolicy(**data)
        except Exception as exc:
            logger.warning("Skipping malformed policy for item %s: %s", item_id, exc)
            return None
