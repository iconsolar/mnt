"""Alembic environment. The URL comes from the app's settings, or from tests."""
from alembic import context
from sqlalchemy import create_engine, pool

import app.auth.models  # noqa: F401  (registers the tables)
import app.people.models  # noqa: F401
from app.config import Settings
from app.db import Base

target_metadata = Base.metadata


def _url() -> str:
    return context.config.attributes.get("database_url") or Settings.from_env().database_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
