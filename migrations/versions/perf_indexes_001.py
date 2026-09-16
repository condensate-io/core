"""Add indexes to speed up entity canonicalization and edge synthesis lookups

Revision ID: perf_indexes_001
Revises: astrocyte_temporal_001
Create Date: 2026-09-16

"""
from alembic import op

revision = "perf_indexes_001"
down_revision = "astrocyte_temporal_001"
branch_labels = None
depends_on = None


def upgrade():
    # Functional index so EntityCanonicalizer.resolve() can do a targeted,
    # normalized lookup on canonical_name scoped to the current batch
    # instead of loading every entity in the project.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_entities_project_normalized_canonical_name "
        "ON entities (project_id, regexp_replace(lower(canonical_name), '^the\\s+', ''))"
    )
    # GIN index over the aliases JSONB array so the `?|` (any-key-exists)
    # fast path in EntityCanonicalizer can use an index scan.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_entities_aliases_gin "
        "ON entities USING GIN (aliases)"
    )
    # Supporting index for latest-per-URI ingest dedup lookup.
    op.create_index(
        "ix_fetched_artifacts_job_source_uri_created_at",
        "fetched_artifacts",
        ["job_id", "source_uri", "created_at"],
    )
    # Deduplicate any pre-existing relation races before enforcing the unique
    # edge identity required by EdgeSynthesizer's ON CONFLICT upsert path.
    op.execute(
        "DELETE FROM relations r1 USING relations r2 "
        "WHERE r1.ctid < r2.ctid "
        "AND r1.project_id = r2.project_id "
        "AND r1.from_id = r2.from_id "
        "AND r1.to_id = r2.to_id "
        "AND r1.relation_type = r2.relation_type"
    )
    op.create_unique_constraint(
        "uq_relations_project_from_to_type",
        "relations",
        ["project_id", "from_id", "to_id", "relation_type"],
    )


def downgrade():
    op.drop_constraint("uq_relations_project_from_to_type", "relations", type_="unique")
    op.drop_index(
        "ix_fetched_artifacts_job_source_uri_created_at",
        table_name="fetched_artifacts",
    )
    op.execute("DROP INDEX IF EXISTS ix_entities_aliases_gin")
    op.execute("DROP INDEX IF EXISTS ix_entities_project_normalized_canonical_name")
