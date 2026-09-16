"""Add indexes to speed up entity canonicalization and edge synthesis lookups

Revision ID: perf_indexes_001
Revises: astrocyte_temporal_001
Create Date: 2026-09-16

"""
from alembic import op
import sqlalchemy as sa

revision = "perf_indexes_001"
down_revision = "astrocyte_temporal_001"
branch_labels = None
depends_on = None


def upgrade():
    # Functional index so EntityCanonicalizer.resolve() can do a targeted,
    # case-insensitive lookup on canonical_name scoped to the current batch
    # instead of loading every entity in the project.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_entities_project_lower_canonical_name "
        "ON entities (project_id, lower(canonical_name))"
    )
    # GIN index over the aliases JSONB array so the `?|` (any-key-exists)
    # containment operator used by EntityCanonicalizer can use an index scan.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_entities_aliases_gin "
        "ON entities USING GIN (aliases)"
    )
    # Composite index so EdgeSynthesizer's single batched SELECT for existing
    # co-occurrence relations among a set of entities is index-backed.
    op.create_index(
        "ix_relations_project_from_to_type",
        "relations",
        ["project_id", "from_id", "to_id", "relation_type"],
    )


def downgrade():
    op.drop_index("ix_relations_project_from_to_type", table_name="relations")
    op.execute("DROP INDEX IF EXISTS ix_entities_aliases_gin")
    op.execute("DROP INDEX IF EXISTS ix_entities_project_lower_canonical_name")
