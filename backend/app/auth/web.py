"""Web sign-in: password, first-login change, then TOTP for those who need it (D-52).

Until every step is done the person is only "pending": a short-lived note in the
session. Flask-Login's sign-in happens at the end, so a half-finished login opens nothing.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, session as cookie, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_user, logout_user

from .. import clock
from ..db import session
from ..people.access import error_text, signed_in
from ..people.models import User
from ..people.service import has_web_access, min_password_length, requires_totp
from . import tokens, totp
from .login import LoginRefused, authenticate, hash_password, register_failure, verify_password

bp = Blueprint("auth", __name__)

PENDING_TTL = timedelta(minutes=10)


def _set_pending(user: User) -> None:
    cookie.clear()
    cookie["pending_uid"] = user.id
    cookie["pending_epoch"] = user.session_epoch
    cookie["pending_at"] = clock.now().isoformat()


def _clear_pending() -> None:
    for key in ("pending_uid", "pending_epoch", "pending_at", "totp_enroll"):
        cookie.pop(key, None)


def _pending_user() -> User | None:
    uid = cookie.get("pending_uid")
    started = cookie.get("pending_at")
    if uid is None or started is None:
        return None
    if clock.now() - datetime.fromisoformat(started) > PENDING_TTL:
        _clear_pending()
        return None
    user = session.get(User, uid)
    if user is None or user.session_epoch != cookie.get("pending_epoch") or not user.is_active or user.is_locked:
        _clear_pending()
        return None
    return user


def _finish(user: User):
    _clear_pending()
    login_user(user)
    return redirect(url_for("web.home"))


def _next_step(user: User):
    if user.must_change_password:
        return redirect(url_for("auth.change_password"))
    if requires_totp(user):
        return redirect(url_for("auth.totp_verify" if totp.is_enrolled(user) else "auth.totp_enroll"))
    return _finish(user)


def _to_login_locked():
    _clear_pending()
    logout_user()
    flash(error_text("account_locked"), "error")
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("web.home"))
    if request.method == "GET":
        return render_template("auth/login.html")

    employee_code = request.form.get("employee_code", "").strip()
    password = request.form.get("password", "")

    def precheck(user: User) -> str | None:
        return None if has_web_access(user) else "no_web_access"

    try:
        user = authenticate(employee_code, password, ip=request.remote_addr, precheck=precheck)
    except LoginRefused as refused:
        flash(error_text(refused.code), "error")
        return render_template("auth/login.html", employee_code=employee_code), 401
    language = cookie.get("lang")
    _set_pending(user)
    if language:
        cookie["lang"] = language
    return _next_step(user)


@bp.post("/logout")
@signed_in(allowed_before_password_change=True)
def logout():
    logout_user()
    cookie.clear()
    return redirect(url_for("auth.login"))


@bp.route("/change-password", methods=["GET", "POST"])
def change_password():
    signed_in_now = current_user.is_authenticated
    user = current_user._get_current_object() if signed_in_now else _pending_user()
    if user is None:
        return redirect(url_for("auth.login"))
    minimum = min_password_length(user)
    if request.method == "GET":
        return render_template("auth/change_password.html", minimum=minimum)

    current = request.form.get("current_password", "")
    new = request.form.get("new_password", "")
    if not verify_password(user.password_hash, current):
        locked = register_failure(user)
        session.commit()
        if locked:
            return _to_login_locked()
        flash(_("auth.password.current_wrong"), "error")
    elif len(new) < minimum:
        flash(error_text("password_too_short", min=minimum), "error")
    elif new != request.form.get("confirm_password", ""):
        flash(_("auth.password.confirm_differs"), "error")
    elif new == current:
        flash(error_text("password_same"), "error")
    else:
        user.password_hash = hash_password(new)
        user.must_change_password = False
        user.failed_logins = 0
        user.session_epoch += 1  # other web sessions of this person end
        tokens.revoke_user_tokens(user.id)  # and the phone signs in again
        session.commit()
        if signed_in_now:
            login_user(user)
            flash(_("auth.password.changed"), "ok")
            return redirect(url_for("web.home"))
        cookie["pending_epoch"] = user.session_epoch
        return _next_step(user)
    return render_template("auth/change_password.html", minimum=minimum), 400


@bp.route("/totp/enroll", methods=["GET", "POST"])
def totp_enroll():
    user = _pending_user()
    if user is None or user.must_change_password or not requires_totp(user):
        return redirect(url_for("auth.login"))
    if totp.is_enrolled(user):
        return redirect(url_for("auth.totp_verify"))

    sealed = cookie.get("totp_enroll")
    secret = totp.decrypt_secret(sealed) if sealed else None
    if secret is None:
        secret = totp.new_secret()
        cookie["totp_enroll"] = totp.encrypt_secret(secret)  # the session cookie is signed, not secret

    if request.method == "POST":
        if totp.code_matches_secret(secret, request.form.get("code", "")):
            codes = totp.complete_enrollment(user, secret)
            session.commit()
            _clear_pending()
            login_user(user)
            return render_template("auth/recovery_codes.html", codes=codes)
        flash(_("auth.totp.invalid"), "error")
    return render_template("auth/totp_enroll.html", qr=totp.provisioning_qr(secret, user), secret=secret)


@bp.route("/totp/verify", methods=["GET", "POST"])
def totp_verify():
    user = _pending_user()
    if user is None or user.must_change_password or not requires_totp(user):
        return redirect(url_for("auth.login"))
    if not totp.is_enrolled(user):
        return redirect(url_for("auth.totp_enroll"))
    if request.method == "GET":
        return render_template("auth/totp_verify.html")

    if totp.verify_code(user, request.form.get("code", "")):
        user.failed_logins = 0
        session.commit()
        return _finish(user)
    locked = register_failure(user)
    session.commit()
    if locked:
        return _to_login_locked()
    flash(_("auth.totp.invalid"), "error")
    return render_template("auth/totp_verify.html"), 401
