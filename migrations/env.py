from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

repo_root = Path(__file__).resolve().parents[1]
sys.path.append(str(repo_root))

from app.schema import Base  # noqa: E402

target_metadata = Base.metadata


def _get_db_url() -> str:
    configured_url = config.get_main_option("sqlalchemy.url")
    if configured_url:
        return configured_url
    db_path = os.getenv("IPAM_DB_PATH", "ipocket.db")
    return f"sqlite:///{db_path}"


def run_migrations_offline() -> None:
    url = _get_db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection")

    if connectable is not None:
        context.configure(
            connection=connectable,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _get_db_url()
    engine = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
