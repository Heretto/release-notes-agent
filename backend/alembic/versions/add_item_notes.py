"""Writer's notes on a release note item

The workspace's "Links" tab (one URL + label per row, table release_note_item_references)
becomes a free-text "Notes" field on the item: context, open questions, and links in prose.
The references table is dropped; anything a person stored there was a URL they can paste
into the new field.

Revision ID: add_item_notes
Revises: add_collaborative_workflow
Create Date: 2026-10-14

NOTE: revision IDs must stay <= 32 characters — alembic_version.version_num is VARCHAR(32).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'add_item_notes'
down_revision = 'add_collaborative_workflow'
branch_labels = None
depends_on = None


def _existing_tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _existing_columns(table):
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    if 'notes' not in _existing_columns('release_note_items'):
        op.add_column('release_note_items', sa.Column('notes', sa.Text(), nullable=True))
    if 'release_note_item_references' in _existing_tables():
        op.drop_table('release_note_item_references')


def downgrade():
    if 'release_note_item_references' not in _existing_tables():
        op.create_table(
            'release_note_item_references',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('item_id', UUID(as_uuid=True), sa.ForeignKey('release_note_items.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('url', sa.Text(), nullable=False),
            sa.Column('label', sa.String(255), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    if 'notes' in _existing_columns('release_note_items'):
        op.drop_column('release_note_items', 'notes')
