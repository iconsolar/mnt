"""Database, migrations, translations and security headers."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from babel.messages.extract import extract_from_dir
from babel.messages.pofile import read_po
from flask_babel import force_locale, gettext as _
from sqlalchemy import text

from app.db import Base, UtcDateTime
from app.db import session as db

BACKEND = Path(__file__).resolve().parents[1]


def test_health_reports_database_ok(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "database": "ok"}


def test_health_needs_no_login_and_unknown_api_path_is_json(client):
    response = client.get("/api/v1/no-such-thing")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_migrations_match_the_models(app):
    with app.extensions["db_engine"].connect() as conn:
        context = MigrationContext.configure(conn, opts={"compare_type": True})
        diff = compare_metadata(context, Base.metadata)
    assert diff == []


def test_tables_are_innodb_utf8mb4(app):
    rows = db.execute(
        text(
            "select table_name, engine, table_collation from information_schema.tables "
            "where table_schema = database() and table_name <> 'alembic_version'"
        )
    ).all()
    assert rows
    for name, engine, collation in rows:
        assert engine == "InnoDB", name
        assert collation == "utf8mb4_0900_ai_ci", name


def test_times_are_stored_as_utc_with_milliseconds(app):
    column = db.execute(
        text(
            "select datetime_precision from information_schema.columns where table_schema = database() "
            "and table_name = 'users' and column_name = 'created_at'"
        )
    ).scalar_one()
    assert column == 3
    kind = UtcDateTime()
    ist = datetime(2026, 11, 4, 9, 0, 0, 123000, tzinfo=timezone.utc).astimezone()
    assert kind.process_bind_param(ist, None).tzinfo is None
    with pytest.raises(ValueError):
        kind.process_bind_param(datetime(2026, 11, 4), None)


def test_every_translation_key_exists_in_all_three_languages():
    keys = set()
    for _file, _line, message, _comments, _ctx in extract_from_dir(
        str(BACKEND),
        method_map=[("app/**.py", "python"), ("app/web/templates/**.html", "jinja2")],
        options_map={"app/web/templates/**.html": {"encoding": "utf-8"}},
    ):
        keys.add(message if isinstance(message, str) else message[0])
    # Keys built at run time in templates.
    keys |= {"language.en", "language.hi", "language.bn"}
    keys |= {"people.status.active", "people.status.blocked", "people.status.left"}
    keys.discard("")
    assert keys, "extraction found nothing"
    for language in ("en", "hi", "bn"):
        path = BACKEND / "app" / "translations" / language / "LC_MESSAGES" / "messages.po"
        with path.open("rb") as f:
            catalog = read_po(f, locale=language)
        missing = sorted(k for k in keys if k not in catalog or not catalog[k].string)
        assert missing == [], f"{language} is missing {missing}"


def test_no_user_facing_key_is_left_as_raw_text_in_hindi_and_bangla(app):
    with app.test_request_context("/"):
        with force_locale("hi"):
            assert _("auth.login.title") == "साइन इन"
        with force_locale("bn"):
            assert _("auth.login.title") == "সাইন ইন"
        with force_locale("en"):
            assert _("auth.login.title") == "Sign in"


def test_login_page_follows_the_browser_language(client):
    page = client.get("/login", headers={"Accept-Language": "hi"}).get_data(as_text=True)
    assert "साइन इन" in page
    assert 'lang="hi"' in page


def test_pages_use_no_external_resources(client):
    response = client.get("/login")
    page = response.get_data(as_text=True)
    assert "http://" not in page and "https://" not in page
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    css = (BACKEND / "app" / "web" / "static" / "css" / "avirat.css").read_text(encoding="utf-8")
    assert "http" not in css


def test_fonts_are_served_locally(client):
    for name in ("noto-sans-latin-400", "noto-sans-devanagari-400", "noto-sans-bengali-400"):
        response = client.get(f"/static/fonts/{name}.woff2")
        assert response.status_code == 200
        response.close()


def test_migrations_can_go_down_and_up_again(migrated, app):
    command.downgrade(migrated, "base")
    command.upgrade(migrated, "head")
    with app.extensions["db_engine"].connect() as conn:
        assert conn.execute(text("select count(*) from users")).scalar_one() == 0
