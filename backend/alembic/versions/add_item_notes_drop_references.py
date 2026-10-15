"""Replace per-note references with a free-text notes field

The workspace Details pane no longer carries a "Links" tab holding a structured list of
URLs. A note now has one free-text `notes` field, shown under the Status/Group fields,
where a person keeps context, open questions and links. URLs in it are linked on render.

Existing references are not discarded: each item's links are folded into its notes text,
one per line, before the table is dropped. That makes this migration lossy only in shape,
not in content.

NOTE: revision IDs must stay <= 32 characters — alembic_version.version_num is
VARCHAR(32), and a longer ID fails the version-table write *after* the DDL runs.

Revision ID: add_item_notes_drop_references
Revises: add_collaborative_workflow
Create Date: 2026-10-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'add_item_notes_drop_references'
down_revision = 'add_collaborative_workflow'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'release_note_items',
        sa.Column('notes', sa.Text(), nullable=False, server_default=''),
    )

    # Fold each item's references into its notes, newest-last, as "label — url" lines.
    # COALESCE keeps items whose notes are already empty rather than nulling them.
    op.execute(r"""
        UPDATE release_note_items AS i
        SET notes = TRIM(BOTH E'\n' FROM COALESCE(i.notes, '') || folded.text)
        FROM (
            SELECT item_id,
                   string_agg(
                       CASE WHEN label IS NOT NULL AND label <> '' THEN label || ' — ' || url ELSE url END,
                       E'\n' ORDER BY created_at
                   ) AS text
            FROM release_note_item_references
            GROUP BY item_id
        ) AS folded
        WHERE i.id = folded.item_id
    """)

    op.drop_table('release_note_item_references')


def downgrade():
    op.create_table(
        'release_note_item_references',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('item_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=True),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['item_id'], ['release_note_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_release_note_item_references_item_id', 'release_note_item_references', ['item_id'])
    # The folded text is left in notes: splitting it back into rows would have to guess
    # which lines were references.
    op.drop_column('release_note_items', 'notes')
