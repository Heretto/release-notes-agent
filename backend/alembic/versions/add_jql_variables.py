"""Add JQL variables to instruction sets and releases

An instruction set's jql_query becomes a template: {name} tokens are filled in when a
release is started. `instruction_sets.variables` describes each token ({name: {label,
default, hint}}); `jobs.variables` records the values a run resolved its query from, so a
run can be explained and rerun without re-deriving them. jobs.jql_query keeps holding the
resolved query that actually ran.

Existing rows get an empty object: a query with no {tokens} has no variables, so every
instruction set written before this behaves exactly as it did.

NOTE: revision IDs must stay <= 32 characters — alembic_version.version_num is
VARCHAR(32), and a longer ID fails the version-table write *after* the DDL runs.

Revision ID: add_jql_variables
Revises: drop_job_ai_credential_id
Create Date: 2026-10-16
"""

from alembic import op
import sqlalchemy as sa

revision = 'add_jql_variables'
down_revision = 'drop_job_ai_credential_id'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'instruction_sets',
        sa.Column('variables', sa.JSON(), nullable=False, server_default='{}'),
    )
    op.add_column(
        'jobs',
        sa.Column('variables', sa.JSON(), nullable=False, server_default='{}'),
    )


def downgrade():
    op.drop_column('jobs', 'variables')
    op.drop_column('instruction_sets', 'variables')
