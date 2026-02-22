import re
import time
from typing import List, Dict, Any, Set

from src.engine.stopwords import (
    get_stop_words,
    TECH_ALLOW_LIST as TECH_TERMS,
    MIN_ENTITY_LENGTH,
)
from src.llm.schemas import ExtractedEntity

# Lazily resolved at first use via get_stop_words()
def _stop_words() -> frozenset:
    return get_stop_words()


class DeterministicCondenser:
    """
    A deterministic approach to memory condensation (L3-Condenser).
    No LLM magic—just rigorous heuristic extraction.
    """
    
    def process(self, text: str) -> Dict[str, Any]:
        start_time = time.time() * 1000
        trace = []
        
        trace.append({"label": "Initializing Memory Tiers...", "timestamp": int(time.time() * 1000), "status": "info"})
        
        # 1. Entity Extraction
        trace.append({"label": "Scanning for Named Entities & Tech Specs...", "timestamp": int(time.time() * 1000), "status": "info"})
        entities = set()
        
        # Regex Patterns
        version_regex = re.compile(r'v\d+\.\d+(?:\.\d+)?', re.IGNORECASE)
        time_regex = re.compile(r'\d+\s?(?:am|pm)', re.IGNORECASE)
        capitalized_regex = re.compile(r'\b[A-Z][a-z]+\b')

        # Matches
        versions = version_regex.findall(text)
        entities.update(versions)
        # time_regex.findall returns groups, need to handle carefully or just match whole string
        for m in time_regex.finditer(text):
            entities.add(m.group(0))
            
        for m in capitalized_regex.finditer(text):
            word = m.group(0)
            # Bound: must be above min length and not a stop word
            if len(word) >= MIN_ENTITY_LENGTH and word.lower() not in _stop_words():
                entities.add(word)
                
        for term in TECH_TERMS:
            if term in text.lower():
                entities.add(term)
        
        # Bound: reject strings that look like code fragments (contain special chars)
        CODE_NOISE = re.compile(r'[\{\}\(\)\[\]"\\=@#<>]')
        entities = {e for e in entities if not CODE_NOISE.search(e)}
        # Bound: case-insensitive dedup — keep the title-cased version where present
        seen_lower: Dict[str, str] = {}
        for e in sorted(entities, key=lambda x: (x.lower() != x)):  # title-case first
            low = e.lower()
            if low not in seen_lower:
                seen_lower[low] = e
        entities = set(seen_lower.values())
        
        # Convert to ExtractedEntity objects
        extracted_entities = []
        for ent_text in entities:
            # Heuristic typing
            ent_type = "concept"
            if ent_text in versions or any(t in ent_text.lower() for t in ['v', 'api', 'auth']):
                ent_type = "artifact"
            elif ent_text.lower() in [t.lower() for t in TECH_TERMS]:
                ent_type = "tool"
            
            extracted_entities.append(ExtractedEntity(
                name=ent_text,
                type=ent_type,
                aliases=[],
                confidence=0.8 # Heuristic confidence
            ))
                
        trace.append({"label": f"Extracted {len(entities)} unique entities", "timestamp": int(time.time() * 1000), "status": "success"})

        # 2. Algorithmic Condensation
        trace.append({"label": "Calculating Semantic Weight...", "timestamp": int(time.time() * 1000), "status": "info"})
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        action_lines = []
        
        for line in lines:
            lower = line.lower()
            if any(key in lower for key in ['need to', 'prioritize', 'focus on', 'meeting', 'bottleneck']):
                # Clean speaker labels
                cleaned = re.sub(r'^(USER|AGENT|BOB|ALICE):\s*', '', line, flags=re.IGNORECASE).strip()
                action_lines.append(cleaned)
                
        condensed = ". ".join(action_lines) if action_lines else "No critical state changes detected in ephemeral context."
        
        # 3. Efficiency
        original_len = len(text)
        condensed_len = len(condensed)
        savings = max(0, int(((original_len - condensed_len) / original_len) * 100)) if original_len > 0 else 0
        
        trace.append({"label": "Delta compression complete", "timestamp": int(time.time() * 1000), "status": "success"})
        trace.append({"label": f"Total processing time: {int(time.time() * 1000 - start_time)}ms", "timestamp": int(time.time() * 1000), "status": "info"})
        
        return {
            "condensed": condensed,
            "entities": extracted_entities, # Now a list of ExtractedEntity objects
            "savings": savings,
            "trace": trace,
            "layer": "Condensed Memory (L3)"
        }
