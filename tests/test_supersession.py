"""Tests for assertion supersession."""

import uuid
from unittest.mock import MagicMock

from src.db.models import Assertion
from src.learn.supersession import apply_supersession, find_conflicting_assertions


def test_find_conflicting_assertions():
    project_id = uuid.uuid4()
    old = Assertion(
        id=uuid.uuid4(),
        project_id=project_id,
        subject_text="Alice",
        predicate="prefers",
        object_text="jasmine tea",
        status="approved",
    )
    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = [old]

    conflicts = find_conflicting_assertions(
        db,
        project_id,
        subject_entity_id=None,
        subject_text="Alice",
        predicate="prefers",
        object_text="green tea",
        object_entity_id=None,
    )
    assert len(conflicts) == 1
    assert conflicts[0].object_text == "jasmine tea"


def test_apply_supersession_updates_old_row():
    project_id = uuid.uuid4()
    old = Assertion(
        id=uuid.uuid4(),
        project_id=project_id,
        subject_text="Alice",
        predicate="prefers",
        object_text="jasmine tea",
        status="approved",
    )
    new = Assertion(
        id=uuid.uuid4(),
        project_id=project_id,
        subject_text="Alice",
        predicate="prefers",
        object_text="green tea",
        status="approved",
    )
    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = [old]

    apply_supersession(db, new)
    assert old.status == "superseded"
    assert old.valid_until is not None
    assert new.supersedes_id == old.id
    db.add.assert_called()
