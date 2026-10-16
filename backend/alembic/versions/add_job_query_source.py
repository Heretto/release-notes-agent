"""Record whether a release's query came from its instruction set

A release stores the query it resolved when it was started, so an instruction set edited
since — a corrected template, a different project, a new filter — never reached a rerun.
A rerun now rebuilds the query from the set as it stands; this column is what stops it
rewriting a query the caller supplied instead.

The backfill decides that for existing rows rather than guessing a default: a release
whose stored query still equals its set's current template came from it, and so did one
that recorded variable values. Anything else is treated as caller-supplied and left alone
on rerun, which is the safe direction to be wrong in.

NOTE: revision IDs must stay <= 32 characters — alembic_version.version_num is
VARCHAR(32), and a longer ID fails the version-table write *after* the DDL runs.

Revision ID: add_job_query_source
Revises: add_comment_resolved
Create Date: 2026-10-16
"""

from alembic import op
import sqlalchemy as sa

revision = 'add_job_query_source'
down_revision = 'add_comment_resolved'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("jobs")}

    if "uses_instruction_query" not in columns:
        op.add_column(
            'jobs',
            sa.Column(
                'uses_instruction_query',
                sa.Boolean(),
                nullable=False,
                server_default='true',
            ),
        )

    # Default to "caller supplied" and only promote the rows we can show came from the set,
    # so a rerun can never silently rewrite a hand-written query.
    op.execute("UPDATE jobs SET uses_instruction_query = false")
    op.execute("""
        UPDATE jobs AS j
        SET uses_instruction_query = true
        FROM instruction_sets AS s
        WHERE j.instruction_set_id = s.id
          AND (j.jql_query = s.jql_query OR j.variables::text NOT IN ('{}', 'null'))
    """)


def downgrade():
    op.drop_column('jobs', 'uses_instruction_query')
