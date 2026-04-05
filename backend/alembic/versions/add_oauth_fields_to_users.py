"""Add OAuth SSO fields to users table

Revision ID: add_oauth_fields_to_users
Revises: add_org_id_to_webhook_configs
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa

revision = 'add_oauth_fields_to_users'
down_revision = 'add_org_id_to_webhook_configs'
branch_labels = None
depends_on = None

def upgrade():
    # Make password_hash nullable for SSO-only users
    op.alter_column('users', 'password_hash', nullable=True)

    # Add OAuth provider fields
    op.add_column('users', sa.Column('oauth_provider', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('oauth_id', sa.String(255), nullable=True))

    # Unique constraint on (oauth_provider, oauth_id) where provider is not null
    op.create_index(
        'uq_users_oauth_provider_id',
        'users',
        ['oauth_provider', 'oauth_id'],
        unique=True,
        postgresql_where=sa.text('oauth_provider IS NOT NULL'),
    )

def downgrade():
    op.drop_index('uq_users_oauth_provider_id', table_name='users')
    op.drop_column('users', 'oauth_id')
    op.drop_column('users', 'oauth_provider')
    op.alter_column('users', 'password_hash', nullable=False)
