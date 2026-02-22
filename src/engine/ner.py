from typing import List, Dict, Any, Set
import logging

logger = logging.getLogger("NER")

class GLiNERWrapper:
    """
    Singleton NER engine backed by GLiNER (Generalist Lightweight NER).
    
    Model: urchade/gliner_small-v2
      - efficient CPU inference
      - schema-conditioned (we pass target labels at runtime)
    """

    _instance = None
    _model = None
    
    # Default labels matching our ontology
    DEFAULT_LABELS = [
        "person", "org", "system", "project", 
        "tool", "concept", "artifact", "location" # Maps to concept
    ]

    MODEL_ID = "urchade/gliner_small-v2"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GLiNERWrapper, cls).__new__(cls)
            cls._instance._load_model()
        return cls._instance

    def _load_model(self):
        try:
            from gliner import GLiNER
            # Load model (downloads if needed)
            self._model = GLiNER.from_pretrained(self.MODEL_ID)
            logger.info(f"GLiNER loaded: {self.MODEL_ID}")
        except ImportError:
            logger.warning("GLiNER library not installed. NER disabled. (pip install gliner)")
            self._model = None
        except Exception as e:
            logger.error(f"Failed to load GLiNER model: {e}")
            self._model = None

    def extract_entities(self, text: str, labels: List[str] = None) -> List[Dict[str, Any]]:
        if not self._model:
            return []
        
        target_labels = labels or self.DEFAULT_LABELS
        
        # Chunking configuration (approx tokens via chars)
        # GLiNER small context is 512 tokens. Safe bet ~1200 chars to avoid truncation warnings.
        CHUNK_SIZE = 1200 
        OVERLAP = 150 

        all_entities = []
        
        # Simple sliding window
        text_len = len(text)
        start = 0
        
        while start < text_len:
            end = min(start + CHUNK_SIZE, text_len)
            chunk_text = text[start:end]
            
            try:
                # Run inference on chunk
                preds = self._model.predict_entities(chunk_text, target_labels, threshold=0.5)
                
                # Adjust offsets and add to list
                for p in preds:
                    p["start"] += start
                    p["end"] += start
                    all_entities.append(p)
                    
            except Exception as e:
                logger.error(f"NER chunk failed: {e}")
            
            if end == text_len:
                break
                
            start += (CHUNK_SIZE - OVERLAP)

        return self._merge_entities(all_entities)

    def _merge_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate entities from overlapping chunks.
        Strategy: Overlapping same-text/same-label entities -> keep highest score.
        """
        if not entities:
            return []
            
        # Key by (start, end, label) -> best_prediction
        merged = {}
        
        for e in entities:
            # GLiNER returns: {start, end, text, label, score}
            key = (e['start'], e['end'], e['label'])
            
            if key in merged:
                if e['score'] > merged[key]['score']:
                    merged[key] = e
            else:
                merged[key] = e
                
        # Sort by start position
        return sorted(merged.values(), key=lambda x: x['start'])


# Singleton accessor
def get_ner_engine() -> GLiNERWrapper:
    return GLiNERWrapper()
