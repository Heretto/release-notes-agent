"""Add review: a reviewer, a reviewed flag, and comments per release note

Review is a separate axis from `status`. `status` is where a note is in the writer's flow
(draft → review → approved); `reviewer_id`/`reviewed` are one person's answer to "have you
read this?", and the two move independently — a note can be approved by the writer without
anyone having reviewed it, or reviewed while still a draft.

Comments are flat, not threaded: a note is short enough that a reply is just the next
comment, and the review screen reads top to bottom.

NOTE: revision IDs must stay <= 32 characters — alembic_version.version_num is
VARCHAR(32), and a longer ID fails the version-table write *after* the DDL runs.

NOTE: `release_note_item_comments` is a brand-new ORM table, so `Base.metadata.create_all()`
at startup will already have created it on a database that has been started since this
model landed. The guard below makes the migration a no-op in that case — the same shape
`add_instruction_set_agents` needed, and for the same reason.

Revision ID: add_item_review
Revises: add_release_source_mode
Create Date: 2026-10-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'add_item_review'
down_revision = 'add_release_source_mode'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    columns = {column["name"] for column in inspector.get_columns("release_note_items")}
    if "reviewer_id" not in columns:
        op.add_column(
            'release_note_items',
            sa.Column('reviewer_id', postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            'fk_release_note_items_reviewer_id_users',
            'release_note_items', 'users',
            ['reviewer_id'], ['id'], ondelete='SET NULL',
        )
    if "reviewed" not in columns:
        op.add_column(
            'release_note_items',
            sa.Column('reviewed', sa.Boolean(), nullable=False, server_default='false'),
        )
    if "reviewed_at" not in columns:
        op.add_column(
            'release_note_items',
            sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        )

    if 'release_note_item_comments' not in inspector.get_table_names():
        op.create_table(
            'release_note_item_comments',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.ForeignKeyConstraint(['item_id'], ['release_note_items.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(
            op.f('ix_release_note_item_comments_item_id'),
            'release_note_item_comments', ['item_id'],
        )


def downgrade():
    op.drop_table('release_note_item_comments')
    op.drop_column('release_note_items', 'reviewed_at')
    op.drop_column('release_note_items', 'reviewed')
    op.drop_column('release_note_items', 'reviewer_id')
