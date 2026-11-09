"""Fold organization guidance into the layout's output guidance

An instruction set had two places to describe its output: `organization_guidance`
(grouping, order and, in practice, house style) and, in the "Describe it" layout mode,
`layout.agent.guidance` (the topic structure). Each reached different agents, so a single
description written in one of them was mostly ignored. There is now one field,
`layout.guidance`, which goes to organize, the writer, the workspace chat and — in
"Describe it" mode — the template agent.

Upgrade, per row: in "Describe it" mode the structure description comes first and the
organization guidance follows it; in the other modes only the organization guidance is
carried over, because the old description belonged to a mode not in use and folding it in
would start sending it to organize and the writer. The old `agent` key is left in the JSON
(nothing reads it) rather than deleted, so that text is not destroyed.

Downgrade puts the guidance back in `organization_guidance` and, in "Describe it" mode,
in `agent.guidance` too: one field cannot be split back into the two it came from.

NOTE: revision IDs must stay <= 32 characters — alembic_version.version_num is
VARCHAR(32), and a longer ID fails the version-table write *after* the DDL runs.

Revision ID: move_org_guidance_to_layout
Revises: add_heretto_credential
Create Date: 2026-11-07
"""

import json

from alembic import op
import sqlalchemy as sa

revision = 'move_org_guidance_to_layout'
down_revision = 'add_heretto_credential'
branch_labels = None
depends_on = None


def _layout(value):
    if isinstance(value, str):
        value = json.loads(value or "{}")
    return value if isinstance(value, dict) else {}


def _columns():
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("instruction_sets")}


def upgrade():
    if "organization_guidance" not in _columns():
        return
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, layout, organization_guidance FROM instruction_sets")).fetchall()
    for row_id, stored, organization in rows:
        layout = _layout(stored)
        agent = layout.get("agent") if isinstance(layout.get("agent"), dict) else {}
        parts = []
        if layout.get("mode") == "agent":
            parts.append((agent.get("guidance") or "").strip())
        parts.append((organization or "").strip())
        # A downgrade writes the one field back into both, so after a round trip they are
        # the same text; joining them again would double it.
        unique = [p for i, p in enumerate(parts) if p and p not in parts[:i]]
        layout["guidance"] = "\n\n".join(unique)
        bind.execute(
            sa.text("UPDATE instruction_sets SET layout = CAST(:layout AS JSON) WHERE id = :id"),
            {"layout": json.dumps(layout), "id": row_id},
        )
    op.drop_column('instruction_sets', 'organization_guidance')


def downgrade():
    if "organization_guidance" not in _columns():
        op.add_column('instruction_sets', sa.Column('organization_guidance', sa.Text(), nullable=True))
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, layout FROM instruction_sets")).fetchall()
    for row_id, stored in rows:
        layout = _layout(stored)
        guidance = layout.pop("guidance", "") or ""
        if layout.get("mode") == "agent":
            layout["agent"] = {"guidance": guidance}
        bind.execute(
            sa.text("UPDATE instruction_sets SET layout = CAST(:layout AS JSON), "
                    "organization_guidance = :guidance WHERE id = :id"),
            {"layout": json.dumps(layout), "guidance": guidance or None, "id": row_id},
        )
