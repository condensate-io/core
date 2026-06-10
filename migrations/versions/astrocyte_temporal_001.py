"""Add temporal-hierarchical fields to assertions for Astrocyte memory strata

Revision ID: astrocyte_temporal_001
Revises: synapse_engine_001
Create Date: 2026-06-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "astrocyte_temporal_001"
down_revision = "synapse_engine_001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "assertions",
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "assertions",
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "assertions",
        sa.Column(
            "supersedes_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assertions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "assertions",
        sa.Column("evidence_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "assertions",
        sa.Column(
            "stratum",
            sa.String(),
            server_default="atomic_assertion",
            nullable=False,
        ),
    )
    op.create_index("ix_assertions_valid_from", "assertions", ["valid_from"])
    op.create_index("ix_assertions_valid_until", "assertions", ["valid_until"])
    op.create_index("ix_assertions_supersedes_id", "assertions", ["supersedes_id"])
    op.create_index("ix_assertions_stratum", "assertions", ["stratum"])

    op.add_column(
        "events",
        sa.Column("stratum", sa.String(), server_default="temporal_event", nullable=False),
    )
    op.add_column(
        "policies",
        sa.Column("stratum", sa.String(), server_default="persona_state", nullable=False),
    )


def downgrade():
    op.drop_column("policies", "stratum")
    op.drop_column("events", "stratum")
    op.drop_index("ix_assertions_stratum", table_name="assertions")
    op.drop_index("ix_assertions_supersedes_id", table_name="assertions")
    op.drop_index("ix_assertions_valid_until", table_name="assertions")
    op.drop_index("ix_assertions_valid_from", table_name="assertions")
    op.drop_column("assertions", "stratum")
    op.drop_column("assertions", "evidence_count")
    op.drop_column("assertions", "supersedes_id")
    op.drop_column("assertions", "valid_until")
    op.drop_column("assertions", "valid_from")
