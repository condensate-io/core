#!/usr/bin/env python3
import json
from pathlib import Path

raw = json.loads(Path("benchmarks/data/locomo10.json").read_text())
samples = raw if isinstance(raw, list) else raw
missing = [
    (s.get("sample_id"), qa)
    for s in samples
    for qa in s.get("qa", [])
    if "answer" not in qa
]
print("missing", len(missing))
for sid, qa in missing[:10]:
    print(sid, qa.get("category"), list(qa.keys()))
