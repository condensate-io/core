"""Load LoCoMo-format benchmark data (snap-research schema, CC BY-NC 4.0).

Condensate-native loader.
Point LOCOMO_DATA_PATH at a downloaded locomo10.json for full runs; CI uses locomo_mini.json.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterator

MINI_PATH = Path(__file__).resolve().parent / "locomo_mini.json"
SESSION_KEY = re.compile(r"^session_(\d+)$")


def resolve_dataset_path(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit
    env_path = os.getenv("LOCOMO_DATA_PATH")
    if env_path:
        return Path(env_path)
    return MINI_PATH


def load_samples(path: Path | None = None) -> list[dict[str, Any]]:
    target = resolve_dataset_path(path)
    if not target.exists():
        raise FileNotFoundError(
            f"LoCoMo dataset not found at {target}. "
            "Use bundled mini fixture or set LOCOMO_DATA_PATH to locomo10.json "
            "(see benchmarks/scripts/fetch_locomo.py)."
        )
    raw = json.loads(target.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and "samples" in raw:
        return raw["samples"]
    raise ValueError(f"Unexpected LoCoMo JSON shape in {target}")


def iter_sessions(conversation: dict[str, Any]) -> Iterator[tuple[int, str | None, list[dict[str, Any]]]]:
    """Yield (session_number, date_time, turns) in chronological order."""
    session_nums: list[int] = []
    for key in conversation:
        match = SESSION_KEY.match(key)
        if match:
            session_nums.append(int(match.group(1)))
    for num in sorted(session_nums):
        turns = conversation.get(f"session_{num}", [])
        if not isinstance(turns, list):
            continue
        date_time = conversation.get(f"session_{num}_date_time")
        yield num, date_time, turns


def conversation_to_messages(conversation: dict[str, Any]) -> list[dict[str, str]]:
    """Flatten multi-session dialog into role/content messages for memory backends."""
    return [
        {"role": msg["role"], "content": msg["content"]}
        for msg in conversation_messages_for_ingest(conversation)
    ]


def conversation_messages_for_ingest(conversation: dict[str, Any]) -> list[dict[str, Any]]:
    """Messages with session metadata for condensate episodic ingest."""
    messages: list[dict[str, Any]] = []
    for session_num, date_time, turns in iter_sessions(conversation):
        session_meta: dict[str, Any] = {"session_num": session_num}
        if date_time:
            session_meta["session_date"] = date_time
        if date_time:
            messages.append(
                {
                    "role": "system",
                    "content": f"[session {session_num} @ {date_time}]",
                    "metadata": dict(session_meta),
                }
            )
        for turn in turns:
            speaker = turn.get("speaker", "unknown")
            text = turn.get("text", "")
            if turn.get("blip_caption"):
                text = f"{text} [image: {turn['blip_caption']}]"
            turn_meta = dict(session_meta)
            dia_id = turn.get("dia_id")
            if dia_id:
                turn_meta["dia_id"] = str(dia_id)
            messages.append(
                {
                    "role": speaker,
                    "content": text,
                    "metadata": turn_meta,
                }
            )
    return messages


def session_summary_messages(sample: dict[str, Any]) -> list[dict[str, Any]]:
    """Session summaries as episodic system messages (explicit dates for temporal QA)."""
    summaries = sample.get("session_summary") or {}
    messages: list[dict[str, Any]] = []
    for key in sorted(summaries.keys()):
        if not key.endswith("_summary"):
            continue
        value = summaries[key]
        if not isinstance(value, str) or not value.strip():
            continue
        match = re.match(r"^session_(\d+)_summary$", key)
        session_num = int(match.group(1)) if match else None
        meta: dict[str, Any] = {"kind": "session_summary"}
        if session_num is not None:
            meta["session_num"] = session_num
        messages.append(
            {
                "role": "system",
                "content": f"[session {session_num} summary] {value.strip()}",
                "metadata": meta,
            }
        )
    return messages


def turn_lookup(conversation: dict[str, Any]) -> dict[str, str]:
    """Map dia_id -> turn text for evidence scoring."""
    lookup: dict[str, str] = {}
    for _, _, turns in iter_sessions(conversation):
        for turn in turns:
            dia_id = turn.get("dia_id")
            if dia_id:
                lookup[str(dia_id)] = turn.get("text", "")
    return lookup


def _flatten_observation_value(value: Any) -> list[str]:
    """Extract fact strings from LoCoMo observation shapes (flat or nested)."""
    lines: list[str] = []
    if isinstance(value, str):
        if value.strip():
            lines.append(value.strip())
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                if item.strip():
                    lines.append(item.strip())
            elif isinstance(item, list) and item:
                fact = str(item[0]).strip()
                if not fact:
                    continue
                if len(item) > 1 and item[1]:
                    lines.append(f"{fact} [{item[1]}]")
                else:
                    lines.append(fact)
            elif isinstance(item, (dict, list)):
                lines.extend(_flatten_observation_value(item))
    elif isinstance(value, dict):
        for nested in value.values():
            lines.extend(_flatten_observation_value(nested))
    return lines


def observation_messages(sample: dict[str, Any]) -> list[dict[str, Any]]:
    """LoCoMo session observations as episodic facts (dia_id provenance for multi-hop)."""
    observation = sample.get("observation") or {}
    messages: list[dict[str, Any]] = []
    for key in sorted(observation.keys()):
        if not key.endswith("_observation"):
            continue
        match = re.match(r"^session_(\d+)_observation$", key)
        session_num = int(match.group(1)) if match else None
        value = observation[key]
        if isinstance(value, dict):
            for speaker, items in value.items():
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, list) or not item:
                        continue
                    fact = str(item[0]).strip()
                    if not fact:
                        continue
                    dia_id = str(item[1]) if len(item) > 1 and item[1] else None
                    meta: dict[str, Any] = {"kind": "observation", "speaker": speaker}
                    if session_num is not None:
                        meta["session_num"] = session_num
                    if dia_id:
                        meta["dia_id"] = dia_id
                    prefix = f"[observation {dia_id}]" if dia_id else "[observation]"
                    messages.append(
                        {
                            "role": "system",
                            "content": f"{prefix} {fact}",
                            "metadata": meta,
                        }
                    )
    return messages


def sample_observations(sample: dict[str, Any]) -> list[str]:
    """Session observations (LoCoMo RAG baseline corpus)."""
    observation = sample.get("observation") or {}
    lines: list[str] = []
    for key in sorted(observation.keys()):
        if not key.endswith("_observation"):
            continue
        lines.extend(_flatten_observation_value(observation[key]))
    return lines


def sample_session_summaries(sample: dict[str, Any]) -> list[str]:
    summaries = sample.get("session_summary") or {}
    lines: list[str] = []
    for key in sorted(summaries.keys()):
        if not key.endswith("_summary"):
            continue
        value = summaries[key]
        if isinstance(value, str) and value.strip():
            lines.append(value.strip())
    return lines


CATEGORY_NAMES: dict[int | str, str] = {
    1: "single-hop",
    2: "temporal",
    3: "multi-hop",
    4: "open-domain",
    5: "adversarial",
}


def normalize_qa(qa: dict[str, Any]) -> dict[str, Any] | None:
    """Map LoCoMo numeric categories and adversarial rows to harness schema."""
    raw_cat = qa.get("category", "unknown")
    cat_name = CATEGORY_NAMES.get(raw_cat, str(raw_cat)) if isinstance(raw_cat, int) else str(raw_cat)

    if raw_cat == 5 or "adversarial_answer" in qa:
        trap = qa.get("adversarial_answer", "")
        return {
            **qa,
            "category": "adversarial",
            "answer": trap,
            "adversarial": True,
            "adversarial_trap": trap,
        }

    if "answer" not in qa:
        return None

    return {**qa, "category": cat_name}


def get_qa_pairs(sample: dict[str, Any]) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for qa in sample.get("qa") or []:
        normalized = normalize_qa(qa)
        if normalized is not None:
            pairs.append(normalized)
    return pairs


def full_transcript_tokens_hint(sample: dict[str, Any], token_counter) -> int:
    """Token count of the entire conversation (efficiency baseline)."""
    messages = conversation_to_messages(sample["conversation"])
    text = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    return token_counter(text)
