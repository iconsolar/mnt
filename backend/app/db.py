"""SQLAlchemy 2 engine, session and declarative base."""
from __future__ import annotations

from datetime import datetime, timezone

from flask import Flask
from sqlalchemy import MetaData, create_engine
from sqlalchemy.dialects.mysql import DATETIME as MYSQL_DATETIME
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker
from sqlalchemy.types import DateTime, TypeDecorator

TABLE_OPTS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}

_NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=_NAMING)
    __table_args__ = TABLE_OPTS


class UtcDateTime(TypeDecorator):
    """UTC in the database as DATETIME(3); aware datetimes in Python.

    A naive datetime is refused, so a local time can never be stored by accident.
    """

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "mysql":
            return dialect.type_descriptor(MYSQL_DATETIME(fsp=3))
        return dialect.type_descriptor(DateTime())

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime refused; pass an aware UTC datetime")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):
        return None if value is None else value.replace(tzinfo=timezone.utc)


SessionFactory = sessionmaker(expire_on_commit=False)
session = scoped_session(SessionFactory)


def init_db(app: Flask, database_url: str) -> None:
    engine = create_engine(database_url, pool_pre_ping=True, pool_recycle=3600)
    SessionFactory.configure(bind=engine)
    app.extensions["db_engine"] = engine

    @app.teardown_appcontext
    def _remove_session(_exc):
        session.remove()
