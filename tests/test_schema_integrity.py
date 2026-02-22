"""
Schema Integrity Tests
======================
These tests connect to the REAL database (not a mock) and verify that the
live Postgres schema matches the SQLAlchemy ORM models.

Why this matters
----------------
SQLAlchemy's `create_all()` only creates tables that don't exist yet.  It
will NOT add new columns to existing tables.  If a developer adds a column
to a model and forgets to write a migration, the app silently breaks at
runtime — exactly what happened with the HITL `reviewed_by` columns.

These tests are skipped automatically when the database is unreachable
(e.g. in a pure-unit CI run without Postgres), so they never block
offline development.  Inside the compose stack they run against the live DB.

Run manually:
    pytest tests/test_schema_integrity.py -v
"""

import os
import pytest
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@condensate-db:5432/condensate",
)

def _db_reachable() -> bool:
    """Return True if we can open a connection to Postgres."""
    try:
        engine = sa.create_engine(DATABASE_URL, connect_args={"connect_timeout": 3})
        with engine.connect():
            pass
        engine.dispose()
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _db_reachable(),
    reason="Live Postgres not reachable — skipping schema integrity tests",
)


@pytest.fixture(scope="module")
def engine():
    eng = sa.create_engine(DATABASE_URL)
    yield eng
    eng.dispose()


@pytest.fixture(scope="module")
def inspector(engine):
    return sa_inspect(engine)


# ---------------------------------------------------------------------------
# Helper: collect ORM model column names per table
# ---------------------------------------------------------------------------

def _orm_columns_for_table(table_name: str) -> dict:
    """
    Return {db_col_name: Column} for every mapped column on the ORM class
    whose __tablename__ matches table_name.

    We use col.name (the actual DB column name) rather than col.key (the
    Python attribute name) so that aliased columns like `metadata_` → `metadata`
    are compared correctly against the live schema.
    """
    from src.db.models import Base
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        if getattr(cls, "__tablename__", None) == table_name:
            return {
                col.name: col  # col.name = DB column name
                for col in mapper.columns
            }
    return {}


def _all_orm_tables() -> list[str]:
    from src.db.models import Base
    return [mapper.class_.__tablename__ for mapper in Base.registry.mappers]


# ---------------------------------------------------------------------------
# 1. Every ORM model column must exist in the live DB table
# ---------------------------------------------------------------------------

@requires_db
class TestColumnPresence:

    TABLES_TO_CHECK = [
        "projects",
        "episodic_items",
        "entities",
        "assertions",
        "events",
        "ontology_nodes",
        "relations",
        "policies",
        "api_keys",
        "data_sources",
        "ingest_jobs",
        "ingest_job_runs",
        "fetched_artifacts",
    ]

    @pytest.mark.parametrize("table_name", TABLES_TO_CHECK)
    def test_table_exists(self, inspector, table_name):
        """The table itself must exist in the DB."""
        tables = inspector.get_table_names()
        assert table_name in tables, (
            f"Table '{table_name}' is defined in the ORM but does not exist in the DB. "
            f"Run init_db() / migrations."
        )

    @pytest.mark.parametrize("table_name", TABLES_TO_CHECK)
    def test_all_orm_columns_present(self, inspector, table_name):
        """Every column on the ORM model must exist in the live table."""
        orm_cols = _orm_columns_for_table(table_name)
        if not orm_cols:
            pytest.skip(f"No ORM mapping found for table '{table_name}'")

        db_cols = {c["name"] for c in inspector.get_columns(table_name)}
        missing = [name for name in orm_cols if name not in db_cols]

        assert not missing, (
            f"Table '{table_name}' is missing columns that are defined in the ORM model: "
            f"{missing}. Add a migration in src/db/session.py::_apply_migrations()."
        )


# ---------------------------------------------------------------------------
# 2. Critical HITL columns on `assertions` — explicit, readable failures
# ---------------------------------------------------------------------------

@requires_db
class TestAssertionHITLColumns:
    """
    Explicit tests for the columns that caused the production outage.
    These give a clear, named failure rather than a parametrised one.
    """

    REQUIRED_HITL_COLUMNS = [
        "reviewed_by",
        "reviewed_at",
        "rejection_reason",
        "instruction_score",
        "safety_score",
    ]

    @pytest.mark.parametrize("col_name", REQUIRED_HITL_COLUMNS)
    def test_hitl_column_exists(self, inspector, col_name):
        db_cols = {c["name"] for c in inspector.get_columns("assertions")}
        assert col_name in db_cols, (
            f"HITL column 'assertions.{col_name}' is missing from the live DB. "
            f"The migration in _apply_migrations() may not have run."
        )

    def test_reviewed_by_is_nullable(self, inspector):
        cols = {c["name"]: c for c in inspector.get_columns("assertions")}
        assert cols["reviewed_by"]["nullable"] is True, (
            "assertions.reviewed_by should be nullable"
        )

    def test_reviewed_at_is_nullable(self, inspector):
        cols = {c["name"]: c for c in inspector.get_columns("assertions")}
        assert cols["reviewed_at"]["nullable"] is True, (
            "assertions.reviewed_at should be nullable"
        )

    def test_rejection_reason_is_nullable(self, inspector):
        cols = {c["name"]: c for c in inspector.get_columns("assertions")}
        assert cols["rejection_reason"]["nullable"] is True, (
            "assertions.rejection_reason should be nullable"
        )


# ---------------------------------------------------------------------------
# 3. Critical indexes must exist
# ---------------------------------------------------------------------------

@requires_db
class TestCriticalIndexes:

    REQUIRED_INDEXES = [
        ("assertions", "ix_assertions_status"),
        ("assertions", "ix_assertions_project_id"),
        ("assertions", "ix_assertions_predicate"),
    ]

    @pytest.mark.parametrize("table_name,index_name", REQUIRED_INDEXES)
    def test_index_exists(self, inspector, table_name, index_name):
        indexes = {idx["name"] for idx in inspector.get_indexes(table_name)}
        assert index_name in indexes, (
            f"Index '{index_name}' on table '{table_name}' is missing. "
            f"Check _apply_migrations() in session.py."
        )


# ---------------------------------------------------------------------------
# 4. _apply_migrations() is idempotent — calling twice must not raise
# ---------------------------------------------------------------------------

@requires_db
def test_apply_migrations_is_idempotent():
    """
    Running _apply_migrations() twice in a row must not raise any exception.
    This guards against non-idempotent SQL (e.g. missing IF NOT EXISTS).
    """
    from src.db.session import _apply_migrations
    _apply_migrations()  # first call (columns already exist)
    _apply_migrations()  # second call — must be a no-op, not an error


# ---------------------------------------------------------------------------
# 5. Unit test (no real DB): init_db() must call _apply_migrations()
# ---------------------------------------------------------------------------

def test_init_db_calls_apply_migrations(monkeypatch):
    """
    Verify the wiring: init_db() must call _apply_migrations() so that
    migrations are always applied on startup, even against an existing DB.
    This test uses mocks — no real DB required.
    """
    import src.db.session as session_module
    from unittest.mock import patch, MagicMock

    mock_engine = MagicMock()
    mock_meta = MagicMock()

    calls = []

    def fake_apply():
        calls.append("_apply_migrations")

    with patch.object(session_module, "engine", mock_engine), \
         patch.object(session_module.Base, "metadata", mock_meta), \
         patch.object(session_module, "_apply_migrations", fake_apply):
        session_module.init_db()

    assert "_apply_migrations" in calls, (
        "init_db() did not call _apply_migrations(). "
        "Schema migrations will not be applied on startup."
    )
    mock_meta.create_all.assert_called_once_with(bind=mock_engine)


# ---------------------------------------------------------------------------
# 6. ORM model vs DB column count sanity check
# ---------------------------------------------------------------------------

@requires_db
@pytest.mark.parametrize("table_name", [
    "assertions", "entities", "projects", "episodic_items",
])
def test_no_extra_db_columns_missing_from_orm(inspector, table_name):
    """
    Warn if the DB has columns that the ORM doesn't know about.
    This is not necessarily an error (e.g. manual DBA columns) but it
    indicates drift and is surfaced as a warning via a soft assertion.
    """
    import warnings

    orm_cols = set(_orm_columns_for_table(table_name).keys())
    db_cols = {c["name"] for c in inspector.get_columns(table_name)}

    # Columns in DB but not in ORM — informational, not a hard failure
    extra_in_db = db_cols - orm_cols
    if extra_in_db:
        warnings.warn(
            f"Table '{table_name}' has DB columns not mapped in the ORM: {extra_in_db}. "
            f"Consider adding them to the model or documenting why they are excluded.",
            UserWarning,
            stacklevel=1,
        )
