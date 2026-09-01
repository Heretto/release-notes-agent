"""Alembic environment for release-notes-agent.

This app's models and hop-core's share one declarative Base, so target_metadata spans both
schemas. Unfiltered, autogenerate writes migrations against tables this app does not own.
The include_object filter below restricts it to ours, and is derived from the models module
rather than hand-listed — a hand-list goes stale, and a table missing from it is excluded
from the comparison entirely, so its changes never reach a migration and the schema drifts
silently. See hop-core AGENTS.md §6.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Import application settings and models
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings
from hop_core.db import Base
import hop_core.models  # noqa: F401  — register hop-core's tables, or foreign keys in ours
                        # cannot resolve and autogenerate dies on NoReferencedTableError
import app.models.database as models  # register ours

# Alembic Config object
config = context.config

# Override sqlalchemy.url from application settings
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate support. This spans hop-core's tables as well as this app's,
# because both are mapped onto the same declarative Base.
target_metadata = Base.metadata


# Tables this application owns, derived from the models module so that adding a model
# cannot silently omit it from migrations.
#
# hop-core AGENTS.md §6 unions in a second clause over bare Table objects found in the
# models namespace. That is deliberately NOT used here: app/models/database.py imports
# hop-core's `user_organizations` association table into its own namespace, so the clause
# would resolve to `organization_members` — a hop-core table — and hand autogenerate
# permission to write migrations against it. This app declares no Table objects of its own,
# so the clause has no upside here.
OUR_TABLES = {
    mapper.class_.__tablename__
    for mapper in Base.registry.mappers
    if mapper.class_.__module__ == models.__name__
}


def include_object(object, name, type_, reflected, compare_to):
    """Restrict autogenerate to tables this application owns."""
    if type_ == "table":
        return name in OUR_TABLES

    # Columns, indexes, and constraints inherit the verdict of the table they hang off.
    parent = getattr(object, "table", None)
    if parent is not None:
        return parent.name in OUR_TABLES

    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
        # SQLite cannot ALTER TABLE in place; batch mode rewrites instead.
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
            # SQLite cannot ALTER TABLE in place; batch mode rewrites instead.
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
