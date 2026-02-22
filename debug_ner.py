
from src.engine.ner import get_ner_engine

def debug_ner():
    ner = get_ner_engine()
    text = "Elon Musk works at SpaceX in Texas."
    print(f"Loading model...")
    # This might trigger download if not cached
    if not ner._model:
        print("Model failed to load/not installed")
        return

    print(f"Extracting from: '{text}'")
    entities = ner.extract_entities(text)
    print("Entities found:")
    for e in entities:
        print(e)

if __name__ == "__main__":
    debug_ner()
