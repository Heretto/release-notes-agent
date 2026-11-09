"""Let a release note item stand for a release with nothing to report

Output guidance can ask for an entry when a product release has issues but none of them
is a change users need to know about ("In version 26.10.22 there are no end-user
updates…"). That entry has no issues of its own, so it is told apart by `kind`, and
`fix_version` records which release it stands for — which is how a rerun knows to retire
it once that release does get a note. Existing rows are all ordinary notes.

NOTE: revision IDs must stay <= 32 characters — alembic_version.version_num is
VARCHAR(32), and a longer ID fails the version-table write *after* the DDL runs.

Revision ID: add_item_kind
Revises: move_org_guidance_to_layout
Create Date: 2026-11-07
"""

from alembic import op
import sqlalchemy as sa

revision = 'add_item_kind'
down_revision = 'move_org_guidance_to_layout'
branch_labels = None
depends_on = None


def upgrade():
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("release_note_items")}
    if "kind" not in columns:
        op.add_column('release_note_items', sa.Column(
            'kind', sa.String(30), nullable=False, server_default='note'))
    if "fix_version" not in columns:
        op.add_column('release_note_items', sa.Column('fix_version', sa.String(255), nullable=True))


def downgrade():
    op.execute("DELETE FROM release_note_items WHERE kind = 'nothing_to_report'")
    op.drop_column('release_note_items', 'fix_version')
    op.drop_column('release_note_items', 'kind')
