"""Add jira_credential_id to instruction_sets

Lets an instruction set pin which Jira credential its JQL query runs against,
instead of always falling back to "any decryptable Jira credential in the org".

Revision ID: add_jira_cred_to_instructions
Revises: add_instruction_set_agents
Create Date: 2026-09-23

NOTE: revision IDs must stay <= 32 characters — alembic_version.version_num is
VARCHAR(32), and a longer ID fails the version-table write *after* the DDL runs.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'add_jira_cred_to_instructions'
down_revision = 'add_instruction_set_agents'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'instruction_sets',
        sa.Column('jira_credential_id', UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_instruction_sets_jira_credential_id',
        'instruction_sets',
        'credentials',
        ['jira_credential_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade():
    op.drop_constraint('fk_instruction_sets_jira_credential_id', 'instruction_sets', type_='foreignkey')
    op.drop_column('instruction_sets', 'jira_credential_id')
