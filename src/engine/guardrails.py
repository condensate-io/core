import re
import os
from typing import Dict, List, Tuple

class InstructionDetector:
    """
    Detects imperative commands and instruction injection attempts in text.
    Returns a confidence score (0.0-1.0) where higher values indicate
    more likely instruction injection.
    """
    
    # Common instruction injection patterns
    INJECTION_PATTERNS = [
        # Flexible ignore/disregard — allow any words between verb and target noun
        r"ignore\s+(?:\w+\s+){0,3}(instructions?|rules?|prompts?|guidelines?)",
        r"disregard\s+(?:\w+\s+){0,3}(instructions?|rules?|guidelines?)",
        r"forget\s+(everything|all|previous)",
        r"(always|never)\s+(respond|answer|say|tell|output)",
        r"from\s+now\s+on",
        r"you\s+(must|should|will|are)\s+(always|never|now)",
        r"your\s+new\s+(role|task|purpose|instruction)",
        r"pretend\s+(you\s+are|to\s+be)",
        r"act\s+as\s+(if|a|an)",
        r"override\s+(previous|all|any)",
    ]
    
    # Imperative verb patterns (commands)
    IMPERATIVE_VERBS = [
        r"^(do|don't|make|create|generate|write|tell|say|respond|answer|output|print|display|show|ignore|forget|disregard|override|change|modify|update|set|enable|disable|turn|activate|deactivate)\s+",
    ]
    
    def __init__(self):
        self.injection_patterns = [re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS]
        self.imperative_patterns = [re.compile(p, re.IGNORECASE) for p in self.IMPERATIVE_VERBS]
    
    def detect(self, text: str) -> Tuple[float, List[str]]:
        """
        Analyze text for instruction injection patterns.
        
        Returns:
            (confidence_score, matched_patterns)
            confidence_score: 0.0-1.0 (higher = more likely instruction)
            matched_patterns: List of matched pattern descriptions
        """
        if not text or len(text.strip()) == 0:
            return 0.0, []
        
        score = 0.0
        matches = []
        
        # 1. Check for explicit injection patterns (high weight)
        for pattern in self.injection_patterns:
            if pattern.search(text):
                score += 0.6
                matches.append(f"Injection pattern: {pattern.pattern}")
        
        # 2. Check for imperative verbs at sentence start (medium weight)
        sentences = text.split('.')
        imperative_count = 0
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            for pattern in self.imperative_patterns:
                if pattern.match(sentence):
                    imperative_count += 1
                    matches.append(f"Imperative verb: {sentence[:50]}")
                    break
        
        if imperative_count > 0:
            # More imperatives = higher score
            imperative_ratio = min(imperative_count / len(sentences), 1.0)
            score += imperative_ratio * 0.3
        
        # 3. Check for meta-instructions about behavior (medium weight)
        meta_patterns = [
            r"you\s+(are|should|must|will)\s+(a|an|the)",
            r"your\s+(purpose|role|task|job)\s+is",
            r"you\s+are\s+designed\s+to",
        ]
        for pattern_str in meta_patterns:
            if re.search(pattern_str, text, re.IGNORECASE):
                score += 0.2
                matches.append(f"Meta-instruction: {pattern_str}")
        
        # 4. Normalize score to 0.0-1.0
        score = min(score, 1.0)
        
        return score, matches


class ContentSafetyFilter:
    """
    Detects overly broad assertions and meta-instructions about system behavior.
    Returns a confidence score (0.0-1.0) where higher values indicate
    more likely safety violations.
    """
    
    BROAD_ASSERTION_PATTERNS = [
        r"(always|never|all|every|none)\s+(users?|people|things?|times?)",
        r"(everything|nothing|everyone|no\s+one)",
        r"in\s+all\s+cases",
        r"without\s+exception",
        # never allow/prevent/permit — command-like prohibitions
        r"never\s+(allow|permit|let|enable|accept|approve)",
    ]
    
    SYSTEM_BEHAVIOR_PATTERNS = [
        r"system\s+(should|must|will|shall)\s+(always|never)",
        r"(enable|disable|turn\s+on|turn\s+off)\s+.*\s+(feature|setting|mode)",
        r"configure\s+.*\s+to",
    ]
    
    def __init__(self):
        self.broad_patterns = [re.compile(p, re.IGNORECASE) for p in self.BROAD_ASSERTION_PATTERNS]
        self.system_patterns = [re.compile(p, re.IGNORECASE) for p in self.SYSTEM_BEHAVIOR_PATTERNS]
    
    def detect(self, text: str) -> Tuple[float, List[str]]:
        """
        Analyze text for safety violations.
        
        Returns:
            (confidence_score, matched_patterns)
            confidence_score: 0.0-1.0 (higher = more likely unsafe)
            matched_patterns: List of matched pattern descriptions
        """
        if not text or len(text.strip()) == 0:
            return 0.0, []
        
        score = 0.0
        matches = []
        
        # 1. Check for overly broad assertions
        for pattern in self.broad_patterns:
            if pattern.search(text):
                score += 0.3
                matches.append(f"Broad assertion: {pattern.pattern}")
        
        # 2. Check for system behavior instructions
        for pattern in self.system_patterns:
            if pattern.search(text):
                score += 0.4
                matches.append(f"System behavior: {pattern.pattern}")
        
        # 3. Normalize score
        score = min(score, 1.0)
        
        return score, matches


class GuardrailEngine:
    """
    Unified guardrail engine that combines instruction detection and content safety.
    """
    
    def __init__(self):
        self.instruction_detector = InstructionDetector()
        self.safety_filter = ContentSafetyFilter()
        
        # Load thresholds from environment
        self.instruction_threshold = float(os.getenv("INSTRUCTION_BLOCK_THRESHOLD", "0.5"))
        self.safety_threshold = float(os.getenv("SAFETY_BLOCK_THRESHOLD", "0.7"))
    
    def check(self, text: str) -> Dict:
        """
        Run all guardrail checks on the text.
        
        Returns:
            {
                "instruction_score": float,
                "instruction_matches": List[str],
                "safety_score": float,
                "safety_matches": List[str],
                "should_block": bool,
                "should_flag": bool
            }
        """
        instruction_score, instruction_matches = self.instruction_detector.detect(text)
        safety_score, safety_matches = self.safety_filter.detect(text)
        
        # Determine if we should block or flag
        should_block = (
            instruction_score >= self.instruction_threshold or
            safety_score >= self.safety_threshold
        )
        
        # Flag if score is above 50% of threshold (early warning)
        should_flag = (
            instruction_score >= self.instruction_threshold * 0.5 or
            safety_score >= self.safety_threshold * 0.5
        )
        
        return {
            "instruction_score": instruction_score,
            "instruction_matches": instruction_matches,
            "safety_score": safety_score,
            "safety_matches": safety_matches,
            "should_block": should_block,
            "should_flag": should_flag
        }
