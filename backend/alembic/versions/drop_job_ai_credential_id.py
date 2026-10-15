"""Drop jobs.ai_credential_id

A job used to name the AI credential its generation ran on. Agents replaced that: an
instruction set names a writer and an analysis agent, each agent names the AI configuration
it runs on, and the pipeline resolves the model through the agent. Nothing has written this
column since, and no UI offered it — it was dead weight carrying a foreign key.

NOTE: revision IDs must stay <= 32 characters — alembic_version.version_num is
VARCHAR(32), and a longer ID fails the version-table write *after* the DDL runs.

Revision ID: drop_job_ai_credential_id
Revises: add_item_notes_drop_references
Create Date: 2026-10-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'drop_job_ai_credential_id'
down_revision = 'add_item_notes_drop_references'
branch_labels = None
depends_on = None


def upgrade():
    # The constraint name depends on whether the column came from
    # add_ai_credential_to_jobs (explicitly named) or from create_all() (auto-named), so
    # drop whatever foreign key is actually on the column rather than guessing a name.
    op.execute("""
        DO $$
        DECLARE constraint_name text;
        BEGIN
            SELECT con.conname INTO constraint_name
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = ANY (con.conkey)
            WHERE rel.relname = 'jobs'
              AND con.contype = 'f'
              AND att.attname = 'ai_credential_id';
            IF constraint_name IS NOT NULL THEN
                EXECUTE format('ALTER TABLE jobs DROP CONSTRAINT %I', constraint_name);
            END IF;
        END $$;
    """)
    op.drop_column('jobs', 'ai_credential_id')


def downgrade():
    op.add_column('jobs', sa.Column('ai_credential_id', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_jobs_ai_credential_id', 'jobs', 'credentials',
        ['ai_credential_id'], ['id'], ondelete='SET NULL',
    )
