"""Make instruction_sets.organization_id non-nullable

Revision ID: make_instruction_set_org_id_non_nullable
Revises: add_jql_to_instructions
Create Date: 2026-03-23
"""

from alembic import op
import sqlalchemy as sa

revision = 'make_instruction_set_org_id_non_nullable'
down_revision = 'add_jql_to_instructions'
branch_labels = None
depends_on = None

def upgrade():
    # Delete any orphaned instruction sets that have no organization
    op.execute(
        "DELETE FROM instruction_sets WHERE organization_id IS NULL"
    )

    # Now make organization_id non-nullable
    op.alter_column(
        'instruction_sets',
        'organization_id',
        nullable=False,
        existing_type=sa.dialects.postgresql.UUID(),
    )

def downgrade():
    op.alter_column(
        'instruction_sets',
        'organization_id',
        nullable=True,
        existing_type=sa.dialects.postgresql.UUID(),
    )
