"""Record which Heretto connection an instruction set's folder is in

A folder id is only meaningful in one Heretto. An organization can have several
connections, and the same id in another one is either missing or a different folder —
so publishing picked "the organization's first Heretto credential that decrypts", which
with more than one connection is a guess.

Existing rows get NULL and keep that fallback, which is correct for the common case of a
single connection. Choosing the folder again records the connection.

NOTE: revision IDs must stay <= 32 characters — alembic_version.version_num is
VARCHAR(32), and a longer ID fails the version-table write *after* the DDL runs.

Revision ID: add_heretto_credential
Revises: add_job_topic_template
Create Date: 2026-10-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'add_heretto_credential'
down_revision = 'add_job_topic_template'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("instruction_sets")}
    if "heretto_credential_id" not in columns:
        op.add_column(
            'instruction_sets',
            sa.Column('heretto_credential_id', postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            'fk_instruction_sets_heretto_credential_id_credentials',
            'instruction_sets', 'credentials',
            ['heretto_credential_id'], ['id'], ondelete='SET NULL',
        )


def downgrade():
    op.drop_column('instruction_sets', 'heretto_credential_id')
