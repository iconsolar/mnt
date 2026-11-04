"""Phone login: employee ID + password, device binding, tokens, my profile."""
from __future__ import annotations

from flask import g, jsonify, request
from sqlalchemy.exc import IntegrityError

from .. import clock
from ..api import bp
from ..db import session
from ..people.access import api_error, signed_in
from ..people.models import User
from ..people.registry import LANGUAGES
from ..people.service import min_password_length
from . import tokens
from .login import LoginRefused, authenticate, hash_password, register_failure, verify_password

_REFUSAL_STATUS = {
    "invalid_credentials": 401,
    "account_locked": 423,
    "account_blocked": 403,
    "device_mismatch": 403,
    "device_in_use": 403,
}


def _text(data: dict, key: str, limit: int) -> str | None:
    value = data.get(key)
    if isinstance(value, str) and 0 < len(value) <= limit:
        return value
    return None


def _profile(user: User, device) -> dict:
    return {
        "id": user.id,
        "employee_code": user.employee_code,
        "name": user.name,
        "phone": user.phone,
        "language": user.language,
        "role": user.role.code,
        "must_change_password": user.must_change_password,
        "permissions": [
            {"screen": p.screen_code, "can_view": p.can_view, "can_act": p.can_act} for p in user.permissions
        ],
        "device": {"install_id": device.install_id, "bound_at": device.bound_at.isoformat()} if device else None,
    }


def _token_body(pair: tokens.TokenPair) -> dict:
    return {
        "access_token": pair.access_token,
        "refresh_token": pair.refresh_token,
        "expires_in": pair.expires_in,
        "token_type": "Bearer",
    }


@bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    employee_code = _text(data, "employee_code", 32)
    password = _text(data, "password", 256)
    install_id = _text(data, "install_id", 64)
    if not (employee_code and password and install_id):
        return api_error("bad_request", 400)

    def precheck(user: User) -> str | None:
        bound = tokens.active_device_of(user)
        if bound is not None and bound.install_id != install_id:
            return "device_mismatch"
        other = tokens.active_device_by_install(install_id)
        if other is not None and other.user_id != user.id:
            return "device_in_use"
        return None

    try:
        user = authenticate(
            employee_code, password, ip=request.remote_addr, install_id=install_id, precheck=precheck
        )
    except LoginRefused as refused:
        return api_error(refused.code, _REFUSAL_STATUS[refused.code])

    device = tokens.active_device_of(user)
    try:
        if device is None:
            device = tokens.bind_device(
                user,
                install_id,
                model=_text(data, "model", 80),
                os_version=_text(data, "os_version", 32),
                app_version=_text(data, "app_version", 32),
            )
        else:
            device.app_version = _text(data, "app_version", 32) or device.app_version
            device.last_seen_at = clock.now()
        pair = tokens.issue_pair(user, device)
        session.commit()
    except IntegrityError:
        # Two logins raced to bind the same phone; the database let one through.
        session.rollback()
        return api_error("device_in_use", 403)
    g.api_user = user
    return jsonify(**_token_body(pair), must_change_password=user.must_change_password, user=_profile(user, device))


@bp.post("/auth/refresh")
def refresh():
    data = request.get_json(silent=True) or {}
    raw = _text(data, "refresh_token", 256)
    install_id = _text(data, "install_id", 64)
    if not (raw and install_id):
        return api_error("bad_request", 400)
    try:
        _user, _device, pair = tokens.refresh(raw, install_id)
    except tokens.TokenRefused as refused:
        return api_error(refused.code, 401)
    session.commit()
    return jsonify(**_token_body(pair))


@bp.post("/auth/logout")
@signed_in(allowed_before_password_change=True)
def logout():
    """Ends this phone's tokens. The phone stays bound."""
    tokens.revoke_device_tokens(g.api_device.id)
    session.commit()
    return jsonify(status="ok")


@bp.post("/auth/change-password")
@signed_in(allowed_before_password_change=True)
def change_password():
    user = g.api_user
    data = request.get_json(silent=True) or {}
    current = _text(data, "current_password", 256)
    new = _text(data, "new_password", 256)
    if not (current and new):
        return api_error("bad_request", 400)
    if not verify_password(user.password_hash, current):
        locked = register_failure(user)
        session.commit()
        return api_error("account_locked", 423) if locked else api_error("invalid_credentials", 401)
    minimum = min_password_length(user)
    if len(new) < minimum:
        return api_error("password_too_short", 400, min=minimum)
    if new == current:
        return api_error("password_same", 400)
    user.password_hash = hash_password(new)
    user.must_change_password = False
    user.failed_logins = 0
    user.session_epoch += 1  # any web session of this person ends
    session.commit()
    return jsonify(status="ok")


@bp.get("/me")
@signed_in
def me():
    return jsonify(_profile(g.api_user, g.api_device))


@bp.put("/me/language")
@signed_in(allowed_before_password_change=True)
def set_language():
    data = request.get_json(silent=True) or {}
    language = data.get("language")
    if language not in LANGUAGES:
        return api_error("invalid_language", 400)
    g.api_user.language = language
    session.commit()
    return jsonify(status="ok", language=language)
