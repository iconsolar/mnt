"""Application factory."""
from __future__ import annotations

from flask import Flask

from .config import Settings
from .logging_setup import configure_logging


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or Settings.from_env()
    configure_logging()

    app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
    app.config.update(
        SECRET_KEY=settings.secret_key,
        AVIRAT=settings,
        SESSION_COOKIE_NAME="avirat_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=settings.env != "test",
        SESSION_COOKIE_SAMESITE="Lax",
    )

    from .api import bp as api_bp

    app.register_blueprint(api_bp)
    return app
