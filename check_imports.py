
import sys
import os
import time

sys.path.append(os.getcwd())

def check_import(module_name):
    print(f"Importing {module_name}...")
    start = time.time()
    try:
        __import__(module_name)
        print(f"  Done in {time.time() - start:.4f}s")
    except Exception as e:
        print(f"  FAILED: {e}")

modules = [
    'pytest',
    'asyncio',
    'uuid',
    'unittest.mock',
    'src.db.models',
    'src.engine.condenser',
    'src.engine.ner',
    'src.learn.canonicalize',
    'src.engine.edge_synthesizer',
    'src.engine.guardrails'
]

for m in modules:
    check_import(m)
