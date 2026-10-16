"""Add the Jira-releases source mode to instruction sets

An instruction set can now get its issues one of two ways. `source_mode = 'jql'` is what
every existing row does: `jql_query` is a template the release fills in. `source_mode =
'releases'` instead reads the fix versions Jira tracks for `jira_project`, and each release
runs `project = X AND fixVersion = "<release>" [AND (extra_jql)] ORDER BY created ASC` —
built by app/services/jql_variables.release_query, never in the browser.

Existing rows get 'jql' and NULL for the two new columns, so they behave exactly as before.

NOTE: revision IDs must stay <= 32 characters — alembic_version.version_num is
VARCHAR(32), and a longer ID fails the version-table write *after* the DDL runs.

Revision ID: add_release_source_mode
Revises: add_jql_variables
Create Date: 2026-10-16
"""

from alembic import op
import sqlalchemy as sa

revision = 'add_release_source_mode'
down_revision = 'add_jql_variables'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'instruction_sets',
        sa.Column('source_mode', sa.String(length=32), nullable=False, server_default='jql'),
    )
    op.add_column('instruction_sets', sa.Column('jira_project', sa.String(length=255), nullable=True))
    op.add_column('instruction_sets', sa.Column('extra_jql', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('instruction_sets', 'extra_jql')
    op.drop_column('instruction_sets', 'jira_project')
    op.drop_column('instruction_sets', 'source_mode')
