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
    def process(self, text: str, ner_entities: List[ExtractedEntity] = None) -> Dict[str, Any]:
        start_time = time.time() * 1000
        trace = []
        
        trace.append({"label": "Initializing Memory Tiers...", "timestamp": int(time.time() * 1000), "status": "info"})
        
        # 1. Entity Extraction
        trace.append({"label": "Scanning for Named Entities & Tech Specs...", "timestamp": int(time.time() * 1000), "status": "info"})
        entities_dict: Dict[str, str] = {} # canonical_name -> type
        
        # Seed with NER entities if provided
        if ner_entities:
            for e in ner_entities:
                entities_dict[e.name] = e.type

        # Regex Patterns for additional items
        version_regex = re.compile(r'v\d+\.\d+(?:\.\d+)?', re.IGNORECASE)
        time_regex = re.compile(r'\d+\s?(?:am|pm)', re.IGNORECASE)
        # Matches TitleCase, ALLCAPS, and SCREAMING_SNAKE_CASE
        entity_pattern = re.compile(r'\b[A-Z]{2,}(?:_[A-Z0-9]+)*\b|\b[A-Z][a-z]+\b')

        # Run regex markers
        for m in version_regex.finditer(text): entities_dict[m.group(0)] = "artifact"
        for m in time_regex.finditer(text): entities_dict[m.group(0)] = "concept"
            
        for m in entity_pattern.finditer(text):
            word = m.group(0)
            if len(word) >= MIN_ENTITY_LENGTH and word.lower() not in _stop_words():
                if word not in entities_dict:
                    entities_dict[word] = "concept"
                
        for term in TECH_TERMS:
            if term in text.lower():
                # Find the actual casing in text
                match = re.search(re.escape(term), text, re.IGNORECASE)
                if match:
                    entities_dict[match.group(0)] = "tool"
        
        # Bound: reject strings that look like code fragments (contain special chars)
        CODE_NOISE = re.compile(r'[\{\}\(\)\[\]"\\=@#<>]')
        clean_entities = {}
        for name, etype in entities_dict.items():
            if not CODE_NOISE.search(name):
                clean_entities[name] = etype

        # Convert to ExtractedEntity objects
        extracted_entities = [
            ExtractedEntity(name=name, type=etype, confidence=0.7)
            for name, etype in clean_entities.items()
        ]
                
        trace.append({"label": f"Resolved {len(clean_entities)} entities (Regex + NER Assisted)", "timestamp": int(time.time() * 1000), "status": "success"})

        # 2. Advanced Heuristic Triplet Extraction (State & Action)
        trace.append({"label": "Running State & Action Extraction...", "timestamp": int(time.time() * 1000), "status": "info"})
        facts = []
        sentences = [s.strip() for s in re.split(r'[\.\?\!]', text) if s.strip()]
        
        # Semantic Patterns
        # Pattern A: [Entity] [Verb] [Value/State] (e.g. Energy is 40%)
        # Pattern B: [Entity] [Action] [Entity] (e.g. Sarah moved to Sector 7G)
        
        action_verbs = ['met', 'entered', 'discussed', 'created', 'updated', 'deleted', 'fixed', 'implemented', 'moved to', 'consumed', 'observed', 'detected']
        state_verbs = ['is', 'at', 'reached', 'detected at']
        
        for sent in sentences:
            sent_entities = [name for name in clean_entities.keys() if name.lower() in sent.lower()]
            if not sent_entities: continue

            # Heuristic Strategy 1: State detection ( [Entity] is [Value] )
            # Look for percentage or numerical values near entities
            val_match = re.search(r'(\d+%\s?|\d+\s?units?)', sent)
            if val_match and sent_entities:
                facts.append({
                    "subject": sent_entities[0],
                    "predicate": "has_level",
                    "object": val_match.group(0).strip(),
                    "confidence": 0.8,
                    "type": "fact"
                })

            # Heuristic Strategy 2: Action Triplet
            for verb in action_verbs:
                v_match = re.search(rf'\b{verb}\b', sent.lower())
                if v_match:
                    v_start = v_match.start()
                    left = [e for e in sent_entities if sent.lower().find(e.lower()) < v_start]
                    right = [e for e in sent_entities if sent.lower().find(e.lower()) > v_start]
                    if left and right:
                        facts.append({
                            "subject": left[-1],
                            "predicate": verb,
                            "object": right[0],
                            "confidence": 0.75,
                            "type": "fact"
                        })
                        break

            # Heuristic Strategy 3: Policy Detection
            policy_match = re.search(r'(?:Policy|Rule|Requirement):\s*([^.]+)', sent, re.IGNORECASE)
            if policy_match:
                facts.append({
                    "subject": "System Policy",
                    "predicate": "defined_as",
                    "object": policy_match.group(1).strip(),
                    "confidence": 0.9,
                    "type": "fact"
                })

        # 3. Algorithmic Condensation (Summary)
        trace.append({"label": "Performing Semantic Distillation...", "timestamp": int(time.time() * 1000), "status": "info"})
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        action_lines = []
        
        for line in lines:
            lower = line.lower()
            if any(key in lower for key in ['need to', 'prioritize', 'focus on', 'meeting', 'bottleneck', 'policy', 'alert', 'critical']):
                cleaned = re.sub(r'^(USER|AGENT|BOB|ALICE|SYSTEM):\s*', '', line, flags=re.IGNORECASE).strip()
                action_lines.append(cleaned)
                
        condensed = ". ".join(action_lines) if action_lines else "No critical state changes detected."
        
        trace.append({"label": f"Knowledge synthesis complete. Facts: {len(facts)}", "timestamp": int(time.time() * 1000), "status": "success"})
        
        return {
            "condensed": condensed,
            "entities": extracted_entities,
            "facts": facts,
            "trace": trace,
            "layer": "Condensed Memory (Heuristic L3)"
        }
