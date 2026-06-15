"""Migrate credentials.type from PostgreSQL ENUM to varchar(50)

hop-core uses String(50) for the credential type column to support an
extensible CredentialTypeRegistry. The old app used a native PostgreSQL
ENUM (credentialtype), which conflicts with hop-core's String mapping.

Revision ID: migrate_credential_type_to_varchar
Revises: add_org_id_to_webhook_configs
Create Date: 2026-06-09
"""

from alembic import op
import sqlalchemy as sa

revision = 'migrate_credential_type_to_varchar'
down_revision = 'add_org_id_to_webhook_configs'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'credentials',
        'type',
        type_=sa.String(50),
        postgresql_using='type::text',
        existing_nullable=False,
    )
    op.execute("DROP TYPE IF EXISTS credentialtype")


def downgrade():
    op.execute("CREATE TYPE credentialtype AS ENUM ('jira', 'heretto', 'gemini', 'openai', 'anthropic')")
    op.alter_column(
        'credentials',
        'type',
        type_=sa.Enum('jira', 'heretto', 'gemini', 'openai', 'anthropic', name='credentialtype'),
        postgresql_using='type::credentialtype',
        existing_nullable=False,
    )
