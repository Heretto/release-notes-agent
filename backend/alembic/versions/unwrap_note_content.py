"""Store a release note's content, not the <div> that held it

A note used to be stored as one ``<div outputclass="release-note" id="rn-…">``. That fixed
the element a note *is*, which is the thing stopping an instruction set from laying its
topics out the way its templates do — notes as ``<li>`` inside one shared ``<ul>``, say.

The wrapper is now assembly's decision, so a note stores only what goes inside it. Assembly
puts that content in whatever element the instruction set asks for and stamps it with the
note's id and ``outputclass="release-note"``, which is the pair the workspace uses to map
rendered DITA back to a note.

This unwraps what is already stored. It is deliberately conservative: a row that does not
parse, or whose content is not a single ``<div>``, is left exactly as it is — the assembler
tolerates both, and guessing at malformed content is how you lose someone's writing.

NOTE: revision IDs must stay <= 32 characters — alembic_version.version_num is
VARCHAR(32), and a longer ID fails the version-table write *after* the DDL runs.

Revision ID: unwrap_note_content
Revises: add_job_query_source
Create Date: 2026-10-16
"""

import logging

from alembic import op
import sqlalchemy as sa
from lxml import etree

revision = 'unwrap_note_content'
down_revision = 'add_job_query_source'
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")

#: Same hardening as the app's parser: no entities, no DTD, no network.
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)


def _inner(dita: str):
    """The children of a single wrapping <div>, serialized. None if that is not the shape."""
    text = (dita or "").strip()
    if not text.startswith("<div"):
        return None
    try:
        div = etree.fromstring(text, _PARSER)
    except etree.XMLSyntaxError:
        return None
    if div.tag != "div":
        return None

    parts = []
    if (div.text or "").strip():
        parts.append(f"<p>{div.text.strip()}</p>")
    for child in div:
        if isinstance(child.tag, str):
            parts.append(etree.tostring(child, encoding="unicode", pretty_print=True).strip())
    return "\n".join(parts).strip() or None


def upgrade():
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, dita_content FROM release_note_items WHERE dita_content <> ''")
    ).fetchall()

    unwrapped = skipped = 0
    for row in rows:
        content = _inner(row.dita_content)
        if content is None:
            skipped += 1
            continue
        connection.execute(
            sa.text("UPDATE release_note_items SET dita_content = :c WHERE id = :i"),
            {"c": content, "i": row.id},
        )
        unwrapped += 1

    logger.info("unwrap_note_content: %d notes unwrapped, %d left as they were", unwrapped, skipped)


def downgrade():
    """Put each note back inside a <div> carrying its id, as it was stored before."""
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, dita_content FROM release_note_items WHERE dita_content <> ''")
    ).fetchall()

    for row in rows:
        content = (row.dita_content or "").strip()
        if content.startswith("<div"):
            continue
        fragment_id = f"rn-{str(row.id).split('-')[0]}"
        connection.execute(
            sa.text("UPDATE release_note_items SET dita_content = :c WHERE id = :i"),
            {
                "c": f'<div id="{fragment_id}" outputclass="release-note">\n{content}\n</div>',
                "i": row.id,
            },
        )
