"""Tests run against a real MySQL test database, built through Alembic."""
from __future__ import annotations

import base64
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from flask import g
from flask.testing import FlaskClient
from sqlalchemy import create_engine, make_url, text

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app import create_app  # noqa: E402
from app.auth.login import hash_password  # noqa: E402
from app.clock import FakeClock  # noqa: E402
from app.config import REPO_ROOT, Settings  # noqa: E402
from app.db import session as db  # noqa: E402
from app.people import service  # noqa: E402
from app.people.models import User  # noqa: E402

START = datetime(2026, 11, 4, 3, 30, tzinfo=timezone.utc)
PASSWORD = "correct-horse"


class IsolatedClient(FlaskClient):
    """Makes each request behave as in production, though the tests hold an app context open.

    Without this, `g` (the signed-in person, the locale) would leak between requests and
    clients, and work a view forgot to commit would still look saved.
    """

    @staticmethod
    def _clear_g():
        for key in list(g):
            g.pop(key)

    def open(self, *args, **kwargs):
        self._clear_g()
        try:
            return super().open(*args, **kwargs)
        finally:
            db.rollback()
            db.expire_all()
            self._clear_g()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    load_dotenv(REPO_ROOT / ".env")
    url = os.environ.get("AVIRAT_TEST_DATABASE_URL", "")
    if not url:
        pytest.exit("AVIRAT_TEST_DATABASE_URL is not set")
    if not (make_url(url).database or "").endswith("_test"):
        pytest.exit("Refusing to run: the test database's name must end in _test")
    return Settings(
        env="test",
        secret_key="test-secret",
        totp_key=base64.urlsafe_b64encode(b"0" * 32).decode(),
        database_url=url,
        base_url="https://avirat.test",
        port=8090,
        timezone="Asia/Kolkata",
    )


@pytest.fixture(scope="session")
def migrated(test_settings):
    engine = create_engine(test_settings.database_url)
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for (table,) in conn.execute(text("SHOW TABLES")).all():
            conn.execute(text(f"DROP TABLE `{table}`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    engine.dispose()
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    config.attributes["database_url"] = test_settings.database_url
    command.upgrade(config, "head")
    return config


@pytest.fixture(scope="session")
def compiled_translations():
    subprocess.run(
        [sys.executable, "-m", "babel.messages.frontend", "compile", "-d", "app/translations", "--statistics"],
        cwd=BACKEND,
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope="session")
def _app(test_settings, migrated, compiled_translations):
    application = create_app(test_settings, clock=FakeClock(START))
    application.test_client_class = IsolatedClient
    return application


@pytest.fixture
def clock(_app) -> FakeClock:
    fake = FakeClock(START)
    _app.extensions["clock"] = fake
    return fake


@pytest.fixture
def app(_app, clock):
    _app.config.update(TESTING=False, WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=False)
    engine = _app.extensions["db_engine"]
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for (table,) in conn.execute(text("SHOW TABLES")).all():
            if table != "alembic_version":
                conn.execute(text(f"DELETE FROM `{table}`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    with _app.app_context():
        service.seed_registry()
        db.commit()
        db.remove()
    ctx = _app.app_context()
    ctx.push()
    yield _app
    db.rollback()
    db.remove()
    ctx.pop()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_user(app):
    def _make(code="E100", role="technician", password=PASSWORD, must_change=False, language="en", name=None) -> User:
        user = service.create_person(
            employee_code=code,
            name=name or f"Person {code}",
            phone=None,
            role=service.role_by_code(role),
            language=language,
            password_hash=hash_password(password),
            actor=None,
        )
        user.must_change_password = must_change
        db.commit()
        return user

    return _make


@pytest.fixture
def web_login():
    """Sign a client in directly, past the password and TOTP steps tested elsewhere."""

    def _login(client, user: User):
        with client.session_transaction() as sess:
            sess["_user_id"] = user.get_id()
            sess["_fresh"] = True
        return client

    return _login
