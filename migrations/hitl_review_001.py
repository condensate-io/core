"""Add HITL review fields to assertions

Revision ID: hitl_review_001
Revises: 
Create Date: 2026-02-18

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'hitl_review_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Update status default
    op.alter_column('assertions', 'status',
                    existing_type=sa.String(),
                    server_default='pending_review')
    
    # Add review fields
    op.add_column('assertions', sa.Column('reviewed_by', sa.String(), nullable=True))
    op.add_column('assertions', sa.Column('reviewed_at', sa.DateTime(), nullable=True))
    op.add_column('assertions', sa.Column('rejection_reason', sa.String(), nullable=True))
    
    # Add guardrail scores
    op.add_column('assertions', sa.Column('instruction_score', sa.Float(), server_default='0.0', nullable=False))
    op.add_column('assertions', sa.Column('safety_score', sa.Float(), server_default='0.0', nullable=False))
    
    # Add index on status for faster queries
    op.create_index('ix_assertions_status', 'assertions', ['status'])


def downgrade():
    op.drop_index('ix_assertions_status', table_name='assertions')
    op.drop_column('assertions', 'safety_score')
    op.drop_column('assertions', 'instruction_score')
    op.drop_column('assertions', 'rejection_reason')
    op.drop_column('assertions', 'reviewed_at')
    op.drop_column('assertions', 'reviewed_by')
    op.alter_column('assertions', 'status',
                    existing_type=sa.String(),
                    server_default='active')
