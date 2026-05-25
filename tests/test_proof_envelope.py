import copy
import uuid
from unittest.mock import MagicMock, patch

import pytest

from src.config import settings
from src.engine.condenser import Condenser, build_proof_envelope, verify_proof_envelope


def test_build_proof_envelope_shape():
    payload = {
        "assertion_id": str(uuid.uuid4()),
        "subject_text": "prod-db",
        "predicate": "is",
        "object_text": "read-only",
        "distilled_at": "2026-02-17T12:00:00Z",
    }
    input_hashes = ["abc123", "def456"]

    envelope = build_proof_envelope(payload, input_hashes)

    assert set(envelope.keys()) == {"payload", "provenance", "signature"}
    assert envelope["payload"] == payload
    assert envelope["provenance"] == {
        "method": "llm-distillation",
        "model": settings.LLM_MODEL,
        "input_hashes": input_hashes,
    }
    assert "inputs" not in envelope
    assert "inputs" not in envelope["provenance"]
    assert envelope["provenance"]["model"] != "gpt-4-mock"


def test_proof_envelope_hmac_signature():
    payload = {
        "assertion_id": str(uuid.uuid4()),
        "subject_text": "prod-db",
        "predicate": "is",
        "object_text": "read-only",
        "distilled_at": "2026-02-17T12:00:00Z",
    }
    envelope = build_proof_envelope(payload, ["hash1"])

    assert verify_proof_envelope(envelope)

    tampered = copy.deepcopy(envelope)
    tampered["payload"]["object_text"] = "read-write"
    assert not verify_proof_envelope(tampered)

    wrong_secret = copy.deepcopy(envelope)
    with patch.object(settings, "CONDENSATE_SECRET", "different-secret"):
        assert not verify_proof_envelope(wrong_secret)


def test_prepare_assertion_uses_rfc_envelope():
    condenser = Condenser(MagicMock())
    fact = {
        "subject": "prod-db",
        "predicate": "is",
        "object": "read-only",
        "confidence": 0.9,
        "evidence": [{"item_id": "item-1", "quote": "db is read-only"}],
    }
    source_hashes = ["sha256_item_1", "sha256_item_2"]

    with patch("src.engine.guardrails.GuardrailEngine") as mock_guardrail_cls:
        mock_guardrail_cls.return_value.check.return_value = {
            "should_block": False,
            "instruction_score": 0.0,
            "safety_score": 0.0,
            "instruction_matches": [],
            "safety_matches": [],
        }

        assertion = condenser._prepare_assertion(uuid.uuid4(), fact, source_hashes)

    assert assertion is not None
    envelope = assertion.provenance[-1]
    assert set(envelope.keys()) == {"payload", "provenance", "signature"}
    assert envelope["payload"]["subject_text"] == "prod-db"
    assert envelope["payload"]["predicate"] == "is"
    assert envelope["payload"]["object_text"] == "read-only"
    assert envelope["payload"]["assertion_id"] == str(assertion.id)
    assert envelope["provenance"]["input_hashes"] == source_hashes
    assert envelope["provenance"]["model"] == settings.LLM_MODEL
    assert verify_proof_envelope(envelope)
