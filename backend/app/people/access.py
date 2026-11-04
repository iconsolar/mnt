"""The permission check on every route.

Every route must either carry a rule (`@requires` or `@signed_in`) or be named in
PUBLIC_ENDPOINTS. A route with neither is refused, and a test fails on it, so a new
route can't be left open by forgetting.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from flask import abort, current_app, g, jsonify, redirect, request, url_for
from flask_babel import gettext as _
from flask_login import current_user

from .registry import N_

log = logging.getLogger("avirat.access")

# The complete list of routes that need no signed-in person. Keep it short.
PUBLIC_ENDPOINTS = frozenset(
    {
        "static",
        "api_v1.health",
        "api_v1.login",  # authenticates by itself
        "api_v1.refresh",  # authenticates by itself, with the refresh token
        "auth.login",
        "auth.change_password",  # first login: checks the pending session or the signed-in person
        "auth.totp_enroll",  # checks the pending session
        "auth.totp_verify",  # checks the pending session
        "web.set_language",
    }
)

_ACCESS_ATTR = "_avirat_access"


@dataclass(frozen=True)
class Rule:
    screen: str | None = None
    action: str = "view"
    allowed_before_password_change: bool = False


def requires(screen: str, action: str = "view"):
    """The person needs this permission on this screen."""

    def mark(view):
        setattr(view, _ACCESS_ATTR, Rule(screen=screen, action=action))
        return view

    return mark


def signed_in(view=None, *, allowed_before_password_change: bool = False):
    """Any signed-in person: their own profile, their own password."""

    def mark(fn):
        setattr(fn, _ACCESS_ATTR, Rule(allowed_before_password_change=allowed_before_password_change))
        return fn

    return mark(view) if view is not None else mark


def rule_of(view) -> Rule | None:
    return getattr(view, _ACCESS_ATTR, None)


API_ERRORS = {
    "unauthorized": N_("api.error.unauthorized"),
    "forbidden": N_("api.error.forbidden"),
    "not_found": N_("api.error.not_found"),
    "method_not_allowed": N_("api.error.method_not_allowed"),
    "server_error": N_("api.error.server_error"),
    "bad_request": N_("api.error.bad_request"),
    "invalid_credentials": N_("api.error.invalid_credentials"),
    "account_locked": N_("api.error.account_locked"),
    "account_blocked": N_("api.error.account_blocked"),
    "device_mismatch": N_("api.error.device_mismatch"),
    "device_in_use": N_("api.error.device_in_use"),
    "no_web_access": N_("api.error.no_web_access"),
    "password_change_required": N_("api.error.password_change_required"),
    "password_too_short": N_("api.error.password_too_short"),
    "password_same": N_("api.error.password_same"),
    "invalid_token": N_("api.error.invalid_token"),
    "token_reused": N_("api.error.token_reused"),
    "invalid_language": N_("api.error.invalid_language"),
}


def error_text(code: str, **params) -> str:
    return _(API_ERRORS[code], **params)


def api_error(code: str, status: int, **params):
    return jsonify(error={"code": code, "message": error_text(code, **params)}), status


def enforce_access():
    endpoint = request.endpoint
    if endpoint is None or endpoint in PUBLIC_ENDPOINTS:
        return None

    rule = rule_of(current_app.view_functions[endpoint])
    is_api = request.blueprint == "api_v1"
    if rule is None:
        log.error("route without a permission rule refused", extra={"endpoint": endpoint})
        return api_error("forbidden", 403) if is_api else abort(403)

    if is_api:
        from ..auth.tokens import authenticate_request

        user = authenticate_request()
        if user is None:
            return api_error("unauthorized", 401)
        g.api_user = user
    else:
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        user = current_user

    if user.must_change_password and not rule.allowed_before_password_change:
        if is_api:
            return api_error("password_change_required", 403)
        return redirect(url_for("auth.change_password"))

    if rule.screen is not None and not user.can(rule.screen, rule.action):
        return api_error("forbidden", 403) if is_api else abort(403)
    return None
