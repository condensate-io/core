"""Add HITL review and OmniSim temporal tracking fields to assertions and relations

Revision ID: hitl_review_001
Revises: initial_schema_001
Create Date: 2026-02-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'hitl_review_001'
down_revision = 'initial_schema_001'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Update status default
    op.alter_column('assertions', 'status',
                    existing_type=sa.String(),
                    server_default='pending_review')
    
    # 2. Add review fields to assertions
    op.add_column('assertions', sa.Column('reviewed_by', sa.String(), nullable=True))
    op.add_column('assertions', sa.Column('reviewed_at', sa.DateTime(), nullable=True))
    op.add_column('assertions', sa.Column('rejection_reason', sa.String(), nullable=True))
    
    # 3. Add guardrail scores to assertions
    op.add_column('assertions', sa.Column('instruction_score', sa.Float(), server_default='0.0', nullable=False))
    op.add_column('assertions', sa.Column('safety_score', sa.Float(), server_default='0.0', nullable=False))
    
    # 4. Add index on status for faster queries
    op.create_index('ix_assertions_status', 'assertions', ['status'])

    # 5. Add OmniSim Temporal Tracking to assertions
    op.add_column('assertions', sa.Column('temporal_step', sa.Integer(), nullable=True))
    op.add_column('assertions', sa.Column('metadata', postgresql.JSONB, server_default='{}', nullable=False))

    # 6. Add OmniSim Temporal Tracking to relations
    op.add_column('relations', sa.Column('temporal_start', sa.Integer(), nullable=True))
    op.add_column('relations', sa.Column('temporal_end', sa.Integer(), nullable=True))
    op.add_column('relations', sa.Column('metadata', postgresql.JSONB, server_default='{}', nullable=False))

    # 7. Add foreign key ON DELETE SET NULL constraint to assertions
    # Drop standard constraints first
    op.drop_constraint('assertions_subject_entity_id_fkey', 'assertions', type_='foreignkey')
    op.drop_constraint('assertions_object_entity_id_fkey', 'assertions', type_='foreignkey')
    # Add cascading set null constraints
    op.create_foreign_key(
        'assertions_subject_entity_id_fkey',
        'assertions', 'entities',
        ['subject_entity_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'assertions_object_entity_id_fkey',
        'assertions', 'entities',
        ['object_entity_id'], ['id'],
        ondelete='SET NULL'
    )

    # 8. Add API Key hashing prefix
    op.add_column('api_keys', sa.Column('prefix', sa.String(), nullable=True))
    op.create_index('ix_api_keys_prefix', 'api_keys', ['prefix'])


def downgrade():
    # Remove prefix from api_keys
    op.drop_index('ix_api_keys_prefix', table_name='api_keys')
    op.drop_column('api_keys', 'prefix')

    # Revert subject/object FK constraints to simple foreign key without ON DELETE SET NULL
    op.drop_constraint('assertions_object_entity_id_fkey', 'assertions', type_='foreignkey')
    op.drop_constraint('assertions_subject_entity_id_fkey', 'assertions', type_='foreignkey')
    op.create_foreign_key(
        'assertions_subject_entity_id_fkey',
        'assertions', 'entities',
        ['subject_entity_id'], ['id']
    )
    op.create_foreign_key(
        'assertions_object_entity_id_fkey',
        'assertions', 'entities',
        ['object_entity_id'], ['id']
    )

    # Remove OmniSim fields from relations
    op.drop_column('relations', 'metadata')
    op.drop_column('relations', 'temporal_end')
    op.drop_column('relations', 'temporal_start')

    # Remove OmniSim fields from assertions
    op.drop_column('assertions', 'metadata')
    op.drop_column('assertions', 'temporal_step')

    # Remove HITL fields from assertions
    op.drop_index('ix_assertions_status', table_name='assertions')
    op.drop_column('assertions', 'safety_score')
    op.drop_column('assertions', 'instruction_score')
    op.drop_column('assertions', 'rejection_reason')
    op.drop_column('assertions', 'reviewed_at')
    op.drop_column('assertions', 'reviewed_by')
    op.alter_column('assertions', 'status',
                    existing_type=sa.String(),
                    server_default='active')
