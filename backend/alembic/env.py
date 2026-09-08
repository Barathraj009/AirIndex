"""Alembic environment script. Not execution-verified in this sandbox
(alembic/sqlalchemy aren't installable here) — written against
Alembic's standard generated template, wired to this project's models
and settings. Run `alembic revision --autogenerate -m "initial schema"`
once installed to confirm it produces the same shape as
deployment/schema_postgres.sql (it should, since both are generated
from/matched against the same SQLAlchemy models in backend/app/models/).
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.models import Base  # noqa: F401 — imports all models so metadata is populated

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override the placeholder URL in alembic.ini with the real one from
# app settings (.env), so there's exactly one place DATABASE_URL lives.
config.set_main_option("sqlalchemy.url", get_settings().database_url_fixed)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
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
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
