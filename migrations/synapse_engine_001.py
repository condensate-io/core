"""Create Synapse Engine tables

Revision ID: synapse_engine_001
Revises: hitl_review_001
Create Date: 2026-05-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'synapse_engine_001'
down_revision = 'hitl_review_001'
branch_labels = None
depends_on = None

def upgrade():
    # memory_synapses table
    op.create_table(
        'memory_synapses',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('from_memory_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('to_memory_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('relation_type', sa.String(), nullable=False, index=True),
        sa.Column('weight', sa.Float(), default=1.0, nullable=False),
        sa.Column('evidence_ids', postgresql.JSONB, server_default='[]', nullable=False),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('decay_rate', sa.Float(), nullable=False),
        sa.Column('last_activated_at', sa.DateTime(), nullable=True)
    )

    # synapse_activations table
    op.create_table(
        'synapse_activations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('synapse_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('memory_synapses.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('relevance_score', sa.Float(), nullable=False),
        sa.Column('context_query', sa.Text(), nullable=True),
        sa.Column('activated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False)
    )

    # consolidated_memories table
    op.create_table(
        'consolidated_memories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('evidence_ids', postgresql.JSONB, server_default='[]', nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False)
    )

def downgrade():
    op.drop_table('consolidated_memories')
    op.drop_table('synapse_activations')
    op.drop_table('memory_synapses')
