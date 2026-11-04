"""Application factory."""
from __future__ import annotations

import logging

from flask import Flask, g, render_template, request, session as flask_session
from flask_babel import get_locale, gettext as _
from flask_login import current_user

from .clock import Clock, SystemClock
from .config import Settings
from .db import init_db
from .db import session as db_session
from .extensions import babel, csrf, login_manager
from .logging_setup import configure_logging

log = logging.getLogger("avirat.web")

# Local files only (no CDN). The TOTP enrolment QR is a data: image.
_CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
    "form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
)


def _select_locale() -> str:
    from .people.registry import LANGUAGES

    user = g.get("api_user")
    if user is None and current_user and current_user.is_authenticated:
        user = current_user
    if user is not None:
        return user.language
    chosen = flask_session.get("lang")
    if chosen in LANGUAGES:
        return chosen
    return request.accept_languages.best_match(LANGUAGES, default="en")


def _load_user(session_id: str):
    from .people.models import User

    try:
        user_id, epoch = (int(part) for part in session_id.split("."))
    except ValueError:
        return None
    user = db_session.get(User, user_id)
    if user is None or user.session_epoch != epoch or not user.is_active or user.is_locked:
        return None
    return user


def _register_errors(app: Flask) -> None:
    from .people.access import api_error

    def handler(status: int, api_code: str, title_key: str):
        def handle(_exc):
            if request.path.startswith("/api/"):
                return api_error(api_code, status)
            return render_template("error.html", title=_(title_key)), status

        return handle

    app.register_error_handler(403, handler(403, "forbidden", "error.forbidden"))
    app.register_error_handler(404, handler(404, "not_found", "error.not_found"))
    app.register_error_handler(405, handler(405, "method_not_allowed", "error.not_found"))
    app.register_error_handler(500, handler(500, "server_error", "error.server"))

    @app.errorhandler(400)
    def bad_request(_exc):
        if request.path.startswith("/api/"):
            return api_error("bad_request", 400)
        return render_template("error.html", title=_("error.bad_request")), 400


def create_app(settings: Settings | None = None, clock: Clock | None = None) -> Flask:
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
        WTF_CSRF_TIME_LIMIT=None,  # the token lives as long as the session
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    )
    app.extensions["clock"] = clock or SystemClock()
    init_db(app, settings.database_url)

    babel.init_app(app, locale_selector=_select_locale)
    app.jinja_env.globals["get_locale"] = get_locale
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.user_loader(_load_user)
    login_manager.session_protection = "basic"

    from .api import bp as api_bp
    from .auth.web import bp as auth_bp
    from .people.access import enforce_access
    from .people.views import bp as people_bp
    from .web.views import bp as web_bp

    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(people_bp)
    app.register_blueprint(web_bp)
    csrf.exempt(api_bp)  # the API authenticates by bearer token, never by cookie

    app.before_request(enforce_access)

    @app.after_request
    def _headers(response):
        response.headers.setdefault("Content-Security-Policy", _CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if request.endpoint != "static":
            response.headers.setdefault("Cache-Control", "no-store")
            log.info(
                "request",
                extra={"method": request.method, "path": request.path, "status": response.status_code, "ip": request.remote_addr},
            )
        return response

    _register_errors(app)

    from .cli import register_cli

    register_cli(app)
    return app
