"""Generate 50 synthetic ContradictionBench cases."""

from __future__ import annotations

import json
from pathlib import Path

TOPICS = [
    ("Server {n}", "down", "up"),
    ("Database {n}", "offline", "online"),
    ("Feature flag {n}", "disabled", "enabled"),
    ("API endpoint {n}", "deprecated", "supported"),
    ("Cache layer {n}", "stale", "fresh"),
]

DATA_PATH = Path(__file__).resolve().parent / "contradiction_cases.json"


def build_cases(count: int = 50) -> list[dict]:
    cases: list[dict] = []
    for i in range(count):
        topic_tpl, neg, pos = TOPICS[i % len(TOPICS)]
        topic = topic_tpl.format(n=i + 1)
        stale = f"{topic} is {neg}"
        active = f"{topic} is {pos}"
        cases.append(
            {
                "id": f"cb-{i + 1:03d}",
                "messages": [
                    {"role": "user", "content": stale, "status": "superseded"},
                    {"role": "user", "content": active, "status": "active"},
                ],
                "query": f"What is the status of {topic}?",
                "expected_active_only": active,
                "forbidden_in_context": [stale],
            }
        )
    return cases


def ensure_cases_file(path: Path | None = None) -> Path:
    target = path or DATA_PATH
    if not target.exists():
        payload = {"version": 1, "cases": build_cases()}
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def load_cases(path: Path | None = None) -> list[dict]:
    target = ensure_cases_file(path)
    data = json.loads(target.read_text(encoding="utf-8"))
    return data["cases"]
