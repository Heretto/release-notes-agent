"""Let a comment be marked resolved

Resolved means "dealt with", not "deleted": the comment stays readable, so what a reviewer
asked for survives next to the change that answered it.

NOTE: revision IDs must stay <= 32 characters — alembic_version.version_num is
VARCHAR(32), and a longer ID fails the version-table write *after* the DDL runs.

NOTE: the columns are guarded. `release_note_item_comments` is young enough that a
database may have had the whole table created by `create_all()` at backend startup, in
which case these columns are already present and `add_column` would fail.

Revision ID: add_comment_resolved
Revises: add_item_review
Create Date: 2026-10-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'add_comment_resolved'
down_revision = 'add_item_review'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("release_note_item_comments")}

    if "resolved" not in columns:
        op.add_column(
            'release_note_item_comments',
            sa.Column('resolved', sa.Boolean(), nullable=False, server_default='false'),
        )
    if "resolved_at" not in columns:
        op.add_column(
            'release_note_item_comments',
            sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        )
    if "resolved_by_id" not in columns:
        op.add_column(
            'release_note_item_comments',
            sa.Column('resolved_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            'fk_release_note_item_comments_resolved_by_id_users',
            'release_note_item_comments', 'users',
            ['resolved_by_id'], ['id'], ondelete='SET NULL',
        )


def downgrade():
    op.drop_column('release_note_item_comments', 'resolved_by_id')
    op.drop_column('release_note_item_comments', 'resolved_at')
    op.drop_column('release_note_item_comments', 'resolved')
