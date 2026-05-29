import uuid

from src.learn.extractor import MemoryExtractor
from src.llm.schemas import ExtractedAssertion


def test_extracted_assertion_accepts_object_alias():
    assertion = ExtractedAssertion(
        subject={"type": "entity", "name": "Alice"},
        predicate="prefers",
        obj={"type": "literal", "value": "tea"},
        polarity=1,
    )
    assert assertion.object == {"type": "literal", "value": "tea"}


def test_memory_extractor_skips_incomplete_assertion():
    extractor = MemoryExtractor()
    item_id = str(uuid.uuid4())
    result = extractor._enrich_assertion(
        {
            "subject": {"type": "person", "name": "Bob"},
            "polarity": 1,
            "confidence": 0.8,
        },
        item_id,
    )
    assert result is None


def test_memory_extractor_keeps_valid_assertions_when_mixed():
    extractor = MemoryExtractor()
    item_id = str(uuid.uuid4())
    parsed = extractor._parse_assertions(
        [
            {"subject": "Alice", "predicate": "uses", "object": "Vim"},
            {"subject": {"type": "person", "name": "Bob"}, "polarity": 1},
            {"subject": "Carol", "predicate": "likes", "obj": "Python"},
        ],
        item_id,
    )
    assert len(parsed) == 2
    assert parsed[0].subject == "Alice"
    assert parsed[1].object == "Python"
