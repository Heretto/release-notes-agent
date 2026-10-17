"""Keep the topic template a run settled on

The agent layout mode describes a topic structure in words and has an agent turn it into
a DITA template. That happens once, at the start of a run, and the result is kept here:
every later assembly of the release — a different topic split, a note edited — uses the
same template, so the shape does not change under the writer, and no model call ever sits
inside a request handler.

Empty in the other layout modes.

NOTE: revision IDs must stay <= 32 characters — alembic_version.version_num is
VARCHAR(32), and a longer ID fails the version-table write *after* the DDL runs.

Revision ID: add_job_topic_template
Revises: add_topic_layout
Create Date: 2026-10-17
"""

from alembic import op
import sqlalchemy as sa

revision = 'add_job_topic_template'
down_revision = 'add_topic_layout'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("jobs")}
    if "topic_template" not in columns:
        op.add_column('jobs', sa.Column('topic_template', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('jobs', 'topic_template')
