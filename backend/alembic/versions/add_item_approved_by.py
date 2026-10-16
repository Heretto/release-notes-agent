"""Record who approved a release note, and when

`status` already said a note was approved; it did not say by whom. The history held it,
but a note should be able to say who signed it off without anyone reading a timeline —
especially now that approving can happen from the review view as well as the workspace.

Both columns are set when the status moves into `approved` and cleared when it moves out,
so they never outlive the approval they describe.

Existing approved notes get NULL: nothing here knows who approved them, and inventing an
approver would be worse than admitting that. The UI shows the plain "Approved" chip for
those, as it did before.

NOTE: revision IDs must stay <= 32 characters — alembic_version.version_num is
VARCHAR(32), and a longer ID fails the version-table write *after* the DDL runs.

Revision ID: add_item_approved_by
Revises: add_comment_resolved
Create Date: 2026-10-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'add_item_approved_by'
down_revision = 'add_comment_resolved'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("release_note_items")}

    if "approved_by_id" not in columns:
        op.add_column(
            'release_note_items',
            sa.Column('approved_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            'fk_release_note_items_approved_by_id_users',
            'release_note_items', 'users',
            ['approved_by_id'], ['id'], ondelete='SET NULL',
        )
    if "approved_at" not in columns:
        op.add_column(
            'release_note_items',
            sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        )


def downgrade():
    op.drop_column('release_note_items', 'approved_at')
    op.drop_column('release_note_items', 'approved_by_id')
