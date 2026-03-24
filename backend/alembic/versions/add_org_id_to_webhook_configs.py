"""Add organization_id to webhook_configs

Revision ID: add_org_id_to_webhook_configs
Revises: make_instruction_set_org_id_non_nullable
Create Date: 2026-03-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'add_org_id_to_webhook_configs'
down_revision = 'make_instruction_set_org_id_non_nullable'
branch_labels = None
depends_on = None

def upgrade():
    # Add organization_id as nullable first
    op.add_column(
        'webhook_configs',
        sa.Column('organization_id', UUID(as_uuid=True), nullable=True),
    )

    # Backfill from the user's current organization
    op.execute("""
        UPDATE webhook_configs wc
        SET organization_id = (
            SELECT om.organization_id
            FROM organization_members om
            WHERE om.user_id = wc.user_id
            LIMIT 1
        )
        WHERE wc.organization_id IS NULL
    """)

    # Delete any rows that couldn't be backfilled (user has no org)
    op.execute("DELETE FROM webhook_configs WHERE organization_id IS NULL")

    # Now make it non-nullable and add the foreign key
    op.alter_column('webhook_configs', 'organization_id', nullable=False)
    op.create_foreign_key(
        'fk_webhook_configs_organization_id',
        'webhook_configs',
        'organizations',
        ['organization_id'],
        ['id'],
        ondelete='CASCADE',
    )

def downgrade():
    op.drop_constraint('fk_webhook_configs_organization_id', 'webhook_configs', type_='foreignkey')
    op.drop_column('webhook_configs', 'organization_id')
