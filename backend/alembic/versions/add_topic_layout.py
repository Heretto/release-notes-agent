"""Add the topic layout to instruction sets

How a topic is laid out — whether a group is a <section> with a title or a bold paragraph,
whether its notes sit in a <ul>, whether each note is a <div> or an <li>, what the
<shortdesc> does — moves from hardcoded to configured. See schemas.TopicLayout.

One JSON column rather than a column per option: the template and agent layout modes that
follow carry quite different settings, and none of them should cost another migration.

Existing rows get {} and are read as the default, which is the shape this app produced
before the column existed — so nothing changes appearance until someone chooses otherwise.

NOTE: revision IDs must stay <= 32 characters — alembic_version.version_num is
VARCHAR(32), and a longer ID fails the version-table write *after* the DDL runs.

Revision ID: add_topic_layout
Revises: unwrap_note_content
Create Date: 2026-10-16
"""

from alembic import op
import sqlalchemy as sa

revision = 'add_topic_layout'
down_revision = 'unwrap_note_content'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("instruction_sets")}
    if "layout" not in columns:
        op.add_column(
            'instruction_sets',
            sa.Column('layout', sa.JSON(), nullable=False, server_default='{}'),
        )


def downgrade():
    op.drop_column('instruction_sets', 'layout')
