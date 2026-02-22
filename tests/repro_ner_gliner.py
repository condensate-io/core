
import logging
import sys
import os

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.engine.ner import get_ner_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ReproNER")

def test_gliner_extraction():
    logger.info("Initializing NER Engine...")
    engine = get_ner_engine()
    
    if not engine._model:
        logger.error("GLiNER model not loaded. Check requirements.")
        return

    # 1. Short text test
    text_short = "Alice works at Acme Corp in New York."
    logger.info(f"Testing short text: '{text_short}'")
    entities = engine.extract_entities(text_short)
    logger.info(f"Entities: {entities}")
    
    assert any(e['text'] == "Alice" and e['label'] == "person" for e in entities)
    assert any(e['text'] == "Acme Corp" and e['label'] == "org" for e in entities)

    # 2. Long text test (for chunking)
    # 2000 chars is chunks size. Let's make 5000 chars.
    logger.info("Testing long text (chunking)...")
    long_text = (
        "Project Apollo was a massive undertaking by NASA. " * 100 + 
        "Finally, Bob Smith launched the rocket. " +
        "The system crashed due to a buffer overflow."
    ) 
    # Length > 4000 chars
    
    entities = engine.extract_entities(long_text, labels=["person", "org", "project", "system", "concept"])
    
    # Check key entities scattered in text
    bobs = [e for e in entities if e['text'] == "Bob Smith"]
    nasas = [e for e in entities if e['text'] == "NASA"]
    projects = [e for e in entities if e['text'] == "Project Apollo"]
    
    logger.info(f"Found {len(nasas)} mentions of NASA")
    logger.info(f"Found Bob: {bobs}")
    
    assert len(nasas) >= 50, "Should catch most NASA mentions across chunks"
    assert len(bobs) >= 1, "Should catch Bob Smith at the end"
    
    logger.info("GLiNER Verification Validation Passed!")

if __name__ == "__main__":
    test_gliner_extraction()
