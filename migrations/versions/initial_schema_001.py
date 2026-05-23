"""Create initial schema for Condensates

Revision ID: initial_schema_001
Revises: 
Create Date: 2026-02-17

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'initial_schema_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. projects table
    op.create_table(
        'projects',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now())
    )

    # 2. episodic_items table
    op.create_table(
        'episodic_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB, server_default='{}', nullable=False),
        sa.Column('qdrant_point_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now())
    )

    # 3. entities table
    op.create_table(
        'entities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('canonical_name', sa.String(), nullable=False),
        sa.Column('aliases', postgresql.JSONB, server_default='[]', nullable=False),
        sa.Column('embedding_ref', sa.String(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('first_seen_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False, server_default=sa.func.now())
    )

    # 4. assertions table
    op.create_table(
        'assertions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('subject_entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('entities.id'), nullable=True),
        sa.Column('subject_text', sa.String(), nullable=True),
        sa.Column('predicate', sa.String(), nullable=False, index=True),
        sa.Column('object_entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('entities.id'), nullable=True),
        sa.Column('object_text', sa.String(), nullable=True),
        sa.Column('polarity', sa.SmallInteger(), nullable=False, server_default='1'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.6', index=True),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.Column('first_seen_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('provenance', postgresql.JSONB, server_default='[]', nullable=False),
        sa.Column('strength', sa.Float(), nullable=False, server_default='1.0', index=True),
        sa.Column('access_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_accessed_at', sa.DateTime(), nullable=True, server_default=sa.func.now())
    )

    # 5. events table
    op.create_table(
        'events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('type', sa.String(), nullable=False, index=True),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('participants', postgresql.JSONB, server_default='[]', nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column('attributes', postgresql.JSONB, server_default='{}', nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.6'),
        sa.Column('provenance', postgresql.JSONB, server_default='[]', nullable=False)
    )

    # 6. ontology_nodes table
    op.create_table(
        'ontology_nodes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('label', sa.String(), nullable=False),
        sa.Column('node_type', sa.String(), nullable=False),
        sa.Column('parent_ids', postgresql.JSONB, server_default='[]', nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('provenance', postgresql.JSONB, server_default='[]', nullable=False)
    )

    # 7. relations table
    op.create_table(
        'relations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('from_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('from_kind', sa.String(), nullable=False),
        sa.Column('relation_type', sa.String(), nullable=False, index=True),
        sa.Column('to_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('to_kind', sa.String(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('provenance', postgresql.JSONB, server_default='[]', nullable=False),
        sa.Column('strength', sa.Float(), nullable=False, server_default='1.0', index=True),
        sa.Column('access_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_accessed_at', sa.DateTime(), nullable=True, server_default=sa.func.now())
    )

    # 8. policies table
    op.create_table(
        'policies',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('trigger', sa.String(), nullable=False, index=True),
        sa.Column('rule', sa.Text(), nullable=False),
        sa.Column('priority', sa.Float(), nullable=False, server_default='0.7', index=True),
        sa.Column('scope', sa.String(), nullable=False, server_default='global'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.7'),
        sa.Column('provenance', postgresql.JSONB, server_default='[]', nullable=False)
    )

    # 9. api_keys table
    op.create_table(
        'api_keys',
        sa.Column('key', sa.String(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now())
    )

    # 10. data_sources table
    op.create_table(
        'data_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('source_type', sa.String(), nullable=False),
        sa.Column('configuration', postgresql.JSONB, server_default='{}', nullable=False),
        sa.Column('cron_schedule', sa.String(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_run', sa.DateTime(), nullable=True)
    )

    # 11. ingest_jobs table
    op.create_table(
        'ingest_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('source_type', sa.String(), nullable=False),
        sa.Column('source_config', postgresql.JSONB, server_default='{}', nullable=False),
        sa.Column('trigger_type', sa.String(), nullable=False),
        sa.Column('trigger_config', postgresql.JSONB, server_default='{}', nullable=False),
        sa.Column('state', sa.String(), nullable=False, server_default='active'),
        sa.Column('idempotency_key', sa.String(), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('next_run_at', sa.DateTime(), nullable=True)
    )

    # 12. ingest_job_runs table
    op.create_table(
        'ingest_job_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ingest_jobs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('status', sa.String(), nullable=False, server_default='queued'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('stats', postgresql.JSONB, server_default='{}', nullable=False),
        sa.Column('cursor', postgresql.JSONB, server_default='{}', nullable=False),
        sa.Column('error_log', sa.Text(), nullable=True)
    )

    # 13. fetched_artifacts table
    op.create_table(
        'fetched_artifacts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ingest_job_runs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ingest_jobs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('source_uri', sa.String(), nullable=False, index=True),
        sa.Column('content_hash', sa.String(), nullable=False, index=True),
        sa.Column('content_type', sa.String(), nullable=False, server_default='text/plain'),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB, server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now())
    )


def downgrade() -> None:
    op.drop_table('fetched_artifacts')
    op.drop_table('ingest_job_runs')
    op.drop_table('ingest_jobs')
    op.drop_table('data_sources')
    op.drop_table('api_keys')
    op.drop_table('policies')
    op.drop_table('relations')
    op.drop_table('ontology_nodes')
    op.drop_table('events')
    op.drop_table('assertions')
    op.drop_table('entities')
    op.drop_table('episodic_items')
    op.drop_table('projects')
