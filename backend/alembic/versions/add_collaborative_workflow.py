"""Collaborative release-notes workflow

Replaces the instruction set's ordered agent chain with role-based agents (writer, analysis),
adds pipeline configuration to instruction sets, pipeline progress to jobs, and the tables the
workspace builds on: Jira issue snapshots, release note items (with their issue links,
personal references and history), assembled topics, and chat messages.

See docs/COLLABORATIVE_WORKFLOW.md.

Revision ID: add_collaborative_workflow
Revises: add_jira_cred_to_instructions
Create Date: 2026-10-14

NOTE: revision IDs must stay <= 32 characters — alembic_version.version_num is VARCHAR(32).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'add_collaborative_workflow'
down_revision = 'add_jira_cred_to_instructions'
branch_labels = None
depends_on = None


def _existing_tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _existing_columns(table):
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _add_column_if_missing(table, column):
    if column.name not in _existing_columns(table):
        op.add_column(table, column)


def upgrade():
    # This app's create_hop_app() lifespan runs Base.metadata.create_all() on every backend
    # startup, so brand-new ORM tables and nullable columns may already exist by the time this
    # migration runs. Every step below is guarded so it is safe either way.
    tables = _existing_tables()

    # ── instruction_sets: role-based agents + pipeline configuration ──────────────────────
    _add_column_if_missing('instruction_sets', sa.Column('writer_agent_id', UUID(as_uuid=True), nullable=True))
    _add_column_if_missing('instruction_sets', sa.Column('analysis_agent_id', UUID(as_uuid=True), nullable=True))
    _add_column_if_missing('instruction_sets', sa.Column('product_name', sa.String(255), nullable=True))
    _add_column_if_missing('instruction_sets', sa.Column('relevance_guidance', sa.Text(), nullable=True))
    _add_column_if_missing('instruction_sets', sa.Column('organization_guidance', sa.Text(), nullable=True))
    _add_column_if_missing('instruction_sets', sa.Column(
        'chunking_strategy', sa.String(40), nullable=False, server_default='single'))

    fks = {fk['name'] for fk in sa.inspect(op.get_bind()).get_foreign_keys('instruction_sets')}
    if 'fk_instruction_sets_writer_agent_id' not in fks:
        op.create_foreign_key('fk_instruction_sets_writer_agent_id', 'instruction_sets', 'agents',
                              ['writer_agent_id'], ['id'], ondelete='SET NULL')
    if 'fk_instruction_sets_analysis_agent_id' not in fks:
        op.create_foreign_key('fk_instruction_sets_analysis_agent_id', 'instruction_sets', 'agents',
                              ['analysis_agent_id'], ['id'], ondelete='SET NULL')

    # The first agent of the old chain becomes the writer; the rest of the chain is dropped.
    if 'instruction_set_agents' in tables:
        op.execute("""
            UPDATE instruction_sets AS s
            SET writer_agent_id = a.agent_id
            FROM instruction_set_agents AS a
            WHERE a.instruction_set_id = s.id
              AND a.position = (
                  SELECT MIN(position) FROM instruction_set_agents WHERE instruction_set_id = s.id
              )
              AND s.writer_agent_id IS NULL
        """)
        op.drop_table('instruction_set_agents')

    # ── jobs: title, progress, chunking, run bookkeeping ─────────────────────────────────
    _add_column_if_missing('jobs', sa.Column('title', sa.String(255), nullable=True))
    _add_column_if_missing('jobs', sa.Column('stage', sa.String(40), nullable=True))
    _add_column_if_missing('jobs', sa.Column('stage_message', sa.Text(), nullable=True))
    _add_column_if_missing('jobs', sa.Column(
        'chunking_strategy', sa.String(40), nullable=False, server_default='single'))
    _add_column_if_missing('jobs', sa.Column('run_count', sa.Integer(), nullable=False, server_default='0'))
    _add_column_if_missing('jobs', sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True))

    # ── new tables ───────────────────────────────────────────────────────────────────────
    if 'job_jira_issues' not in tables:
        op.create_table(
            'job_jira_issues',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('job_id', UUID(as_uuid=True), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('issue_key', sa.String(64), nullable=False),
            sa.Column('url', sa.Text(), nullable=True),
            sa.Column('summary', sa.Text(), nullable=False, server_default=''),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('issue_type', sa.String(100), nullable=True),
            sa.Column('status', sa.String(100), nullable=True),
            sa.Column('priority', sa.String(100), nullable=True),
            sa.Column('labels', sa.JSON(), nullable=False),
            sa.Column('components', sa.JSON(), nullable=False),
            sa.Column('fix_versions', sa.JSON(), nullable=False),
            sa.Column('comments', sa.JSON(), nullable=False),
            sa.Column('assignee', sa.String(255), nullable=True),
            sa.Column('reporter', sa.String(255), nullable=True),
            sa.Column('jira_created', sa.String(64), nullable=True),
            sa.Column('jira_updated', sa.String(64), nullable=True),
            sa.Column('content_hash', sa.String(64), nullable=False),
            sa.Column('relevance', sa.String(20), nullable=False, server_default='pending'),
            sa.Column('relevance_reason', sa.Text(), nullable=True),
            sa.Column('in_query', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('first_seen_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('changed_at', sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint('job_id', 'issue_key', name='uq_job_jira_issues_job_key'),
        )

    if 'release_note_topics' not in tables:
        op.create_table(
            'release_note_topics',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('job_id', UUID(as_uuid=True), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('slug', sa.String(255), nullable=False),
            sa.Column('title', sa.String(500), nullable=False),
            sa.Column('filename', sa.String(255), nullable=False),
            sa.Column('dita_content', sa.Text(), nullable=False, server_default=''),
            sa.Column('heretto_doc_id', sa.String(255), nullable=True),
            sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        )

    if 'release_note_items' not in tables:
        op.create_table(
            'release_note_items',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('job_id', UUID(as_uuid=True), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('topic_id', UUID(as_uuid=True), sa.ForeignKey('release_note_topics.id', ondelete='SET NULL'), nullable=True),
            sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('group_name', sa.String(255), nullable=True),
            sa.Column('title', sa.String(500), nullable=False),
            sa.Column('summary', sa.Text(), nullable=False, server_default=''),
            sa.Column('dita_content', sa.Text(), nullable=False, server_default=''),
            sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
            sa.Column('needs_attention', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('attention_reason', sa.Text(), nullable=True),
            sa.Column('user_edited', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        )

    if 'release_note_item_issues' not in tables:
        op.create_table(
            'release_note_item_issues',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('item_id', UUID(as_uuid=True), sa.ForeignKey('release_note_items.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('issue_id', UUID(as_uuid=True), sa.ForeignKey('job_jira_issues.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.UniqueConstraint('item_id', 'issue_id', name='uq_release_note_item_issue'),
        )

    if 'release_note_item_references' not in tables:
        op.create_table(
            'release_note_item_references',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('item_id', UUID(as_uuid=True), sa.ForeignKey('release_note_items.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('url', sa.Text(), nullable=False),
            sa.Column('label', sa.String(255), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if 'release_note_item_history' not in tables:
        op.create_table(
            'release_note_item_history',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('item_id', UUID(as_uuid=True), sa.ForeignKey('release_note_items.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('event_type', sa.String(40), nullable=False),
            sa.Column('actor', sa.String(20), nullable=False, server_default='system'),
            sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('summary', sa.Text(), nullable=False),
            sa.Column('details', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if 'release_note_chat_messages' not in tables:
        op.create_table(
            'release_note_chat_messages',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('job_id', UUID(as_uuid=True), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('role', sa.String(20), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('actions', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )


def downgrade():
    for table in (
        'release_note_chat_messages', 'release_note_item_history', 'release_note_item_references',
        'release_note_item_issues', 'release_note_items', 'release_note_topics', 'job_jira_issues',
    ):
        op.drop_table(table)

    for column in ('last_run_at', 'run_count', 'chunking_strategy', 'stage_message', 'stage', 'title'):
        op.drop_column('jobs', column)

    op.create_table(
        'instruction_set_agents',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('instruction_set_id', UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', UUID(as_uuid=True), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['instruction_set_id'], ['instruction_sets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_instruction_set_agents_instruction_set_id', 'instruction_set_agents', ['instruction_set_id'])
    op.execute("""
        INSERT INTO instruction_set_agents (id, instruction_set_id, agent_id, position)
        SELECT gen_random_uuid(), id, writer_agent_id, 0 FROM instruction_sets WHERE writer_agent_id IS NOT NULL
    """)

    op.drop_constraint('fk_instruction_sets_analysis_agent_id', 'instruction_sets', type_='foreignkey')
    op.drop_constraint('fk_instruction_sets_writer_agent_id', 'instruction_sets', type_='foreignkey')
    for column in ('chunking_strategy', 'organization_guidance', 'relevance_guidance',
                   'product_name', 'analysis_agent_id', 'writer_agent_id'):
        op.drop_column('instruction_sets', column)
