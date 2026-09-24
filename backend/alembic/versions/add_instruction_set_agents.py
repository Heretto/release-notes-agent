"""Replace instruction/job free-text instructions with an ordered agent chain

Adds instruction_set_agents (an ordered join to hop-core's agents table) and
drops the now-superseded system_prompt / user_instructions / additional_instructions
columns. See release-notes-agent AGENTS.md for the Agents migration this backs.

Revision ID: add_instruction_set_agents
Revises: cb46c0870827
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'add_instruction_set_agents'
down_revision = 'cb46c0870827'
branch_labels = None
depends_on = None


def upgrade():
    # This app's create_hop_app() lifespan runs Base.metadata.create_all() on every backend
    # startup. Every prior migration here only ever added columns to tables that already
    # existed, so create_all() never touched them — but instruction_set_agents is a brand new
    # ORM table, so create_all() will have already created it (with no data) the moment the
    # backend was started against this database, before this migration ever ran. Guard the
    # create so this migration is safe whether or not that already happened.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'instruction_set_agents' not in existing_tables:
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

    existing_indexes = {
        ix['name'] for ix in inspector.get_indexes('instruction_set_agents')
    }
    if 'ix_instruction_set_agents_instruction_set_id' not in existing_indexes:
        op.create_index(
            'ix_instruction_set_agents_instruction_set_id',
            'instruction_set_agents',
            ['instruction_set_id'],
        )

    op.drop_column('instruction_sets', 'system_prompt')
    op.drop_column('instruction_sets', 'user_instructions')
    op.drop_column('jobs', 'additional_instructions')


def downgrade():
    op.add_column('jobs', sa.Column('additional_instructions', sa.Text(), nullable=True))
    op.add_column('instruction_sets', sa.Column('user_instructions', sa.Text(), nullable=True))
    op.add_column(
        'instruction_sets',
        sa.Column('system_prompt', sa.Text(), nullable=False, server_default=''),
    )
    op.alter_column('instruction_sets', 'system_prompt', server_default=None)

    op.drop_index('ix_instruction_set_agents_instruction_set_id', table_name='instruction_set_agents')
    op.drop_table('instruction_set_agents')
