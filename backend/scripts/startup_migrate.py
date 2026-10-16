"""Bring the database to the current schema, then exit.

Run as a one-shot container before the backend and the Celery worker start, so a deploy
does not need a manual `alembic upgrade head`. Both of those services are built from this
image, so the work lives here rather than in an entrypoint: two containers running DDL
against one database at the same time is how you get a half-applied migration.

The three cases mirror install.sh, because this project does not create its baseline schema
with Alembic — `create_all()` does, and the migrations are incremental patches layered on
top (see AGENTS.md):

  empty database        create_all() builds the current schema, then stamp head, because
                        replaying migrations over tables that are already current fails.
  stamped database      upgrade head — the normal path.
  tables, no stamp      refuse. The schema could be any age, so neither stamping (skips
                        real migrations) nor upgrading (re-applies applied ones) is safe to
                        guess at. An operator stamps the right revision by hand, once.
  several revisions     refuse, when the graph has only one head: the version table is
                        corrupted, and Alembic's own error for it names neither the stale
                        row nor the fix.
"""

from __future__ import annotations

import sys

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.config import get_settings
from hop_core.db import init_engine, get_engine
import app.models.database  # noqa: F401 — registers this app's tables on the shared Base
from app.models.database import Base


def main() -> int:
    settings = get_settings()
    init_engine(settings.database_url)
    engine = get_engine()

    table_names = set(inspect(engine).get_table_names())
    stamped = "alembic_version" in table_names
    app_tables = table_names - {"alembic_version"}

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", settings.database_url)

    if not app_tables:
        Base.metadata.create_all(bind=engine)
        command.stamp(config, "head")
        print("migrate: empty database — schema created and stamped at head", flush=True)
        return 0

    if not stamped:
        print(
            "migrate: refusing to guess. The database has tables but no alembic_version, so "
            "its schema version is unknown. Stamp the revision it actually matches, once:\n"
            "    docker compose run --rm migrate alembic stamp <revision>\n"
            "then start the stack again.",
            file=sys.stderr,
            flush=True,
        )
        return 1

    stamped_revisions = _stamped_revisions(engine)
    heads = ScriptDirectory.from_config(config).get_heads()
    if len(stamped_revisions) > 1 and len(heads) == 1:
        # Several rows are legitimate only when the graph really has several heads. With one
        # head they are a corrupted version table — usually an ancestor left behind beside
        # its descendant — and Alembic reports it as an unhelpful "requested revision
        # overlaps with other requested revisions". Name it instead.
        print(
            "migrate: alembic_version holds more than one revision "
            f"({', '.join(sorted(stamped_revisions))}) but the migrations have a single head "
            f"({heads[0]}). One of those rows is stale. Work out which revision the schema "
            "actually matches, delete the other row, then start again:\n"
            "    delete from alembic_version where version_num = '<stale revision>';",
            file=sys.stderr,
            flush=True,
        )
        return 1

    command.upgrade(config, "head")
    print("migrate: upgraded to head", flush=True)
    return 0


def _stamped_revisions(engine) -> list[str]:
    with engine.connect() as connection:
        return [row[0] for row in connection.execute(text("select version_num from alembic_version"))]


if __name__ == "__main__":
    sys.exit(main())
