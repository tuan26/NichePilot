"""Alembic env (T029). URL lấy từ `config.attributes['database_url']` (test) hoặc biến DATABASE_URL."""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine, pool

from nichepilot.core.models_base import Base
from nichepilot.db_models import import_all_models

import_all_models()
target_metadata = Base.metadata
config = context.config


def _url() -> str:
    url = config.attributes.get("database_url") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("Thiếu DATABASE_URL cho migration")
    return str(url)


def _include_name(name: str | None, type_: str, _parent: object) -> bool:
    return not (type_ == "table" and (name or "").startswith("procrastinate_"))


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True, include_name=_include_name)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_name=_include_name,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
