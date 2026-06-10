"""Tests for answer-aware memory feedback."""

import uuid
from unittest.mock import MagicMock

from src.db.models import Assertion
from src.engine.feedback import MemoryFeedbackService


def test_feedback_strengthens_on_correct():
    db = MagicMock()
    id_a = uuid.uuid4()
    id_b = uuid.uuid4()
    assertion = Assertion(id=id_a, strength=1.0, provenance=[], access_count=0)
    db.query.return_value.filter.return_value.all.return_value = [assertion]
    db.query.return_value.filter.return_value.update.return_value = 0

    service = MemoryFeedbackService(db)
    outcome = service.apply_feedback([id_a, id_b], correct=True)
    assert outcome["strengthened"] == 2
    db.commit.assert_called()


def test_feedback_decays_on_incorrect():
    db = MagicMock()
    db.query.return_value.filter.return_value.update.return_value = 2
    service = MemoryFeedbackService(db)
    outcome = service.apply_feedback([uuid.uuid4(), uuid.uuid4()], correct=False)
    assert outcome["decayed"] == 2
