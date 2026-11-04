"""Web screens: people, permissions, unlock, device reset, password reset."""
from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user
from sqlalchemy import or_, select

from ..auth import tokens
from ..auth.login import hash_password, unlock
from ..db import session
from . import audit, service
from .access import requires
from .models import Screen, User
from .registry import LANGUAGES, SCREENS

bp = Blueprint("people", __name__, url_prefix="/people")

STATUSES = ("active", "blocked", "left")
LIST_LIMIT = 200


def _target_or_403(user_id: int) -> User:
    """A person the signed-in person may manage. The rank rule lives on the server."""
    target = session.get(User, user_id)
    if target is None:
        abort(404)
    if not service.can_manage(current_user, target):
        abort(403)
    return target


@bp.get("/")
@requires("people")
def index():
    query = request.args.get("q", "").strip()
    stmt = select(User).order_by(User.employee_code).limit(LIST_LIMIT)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(or_(User.employee_code.like(like), User.name.like(like)))
    people = list(session.scalars(stmt))
    devices = {d.user_id: d for d in (tokens.active_device_of(p) for p in people) if d is not None}
    return render_template(
        "people/index.html", people=people, devices=devices, query=query, can_manage=service.can_manage
    )


def _form_values() -> dict:
    return {
        "employee_code": request.form.get("employee_code", "").strip(),
        "name": request.form.get("name", "").strip(),
        "phone": request.form.get("phone", "").strip(),
        "language": request.form.get("language", "en"),
        "role": request.form.get("role", ""),
        "status": request.form.get("status", "active"),
    }


def _chosen_role(code: str):
    allowed = {r.code: r for r in service.assignable_roles(current_user)}
    return allowed.get(code)


@bp.route("/new", methods=["GET", "POST"])
@requires("people", "act")
def new():
    roles = service.assignable_roles(current_user)
    if request.method == "GET":
        return render_template("people/form.html", person=None, values={}, roles=roles, languages=LANGUAGES)

    values = _form_values()
    role = _chosen_role(values["role"])
    error = None
    if not values["employee_code"] or len(values["employee_code"]) > 32 or not values["name"]:
        error = _("people.error.required")
    elif role is None:
        error = _("people.error.role")
    elif session.scalar(select(User).where(User.employee_code == values["employee_code"])) is not None:
        error = _("people.error.duplicate")
    if error:
        flash(error, "error")
        return render_template("people/form.html", person=None, values=values, roles=roles, languages=LANGUAGES), 400

    password = service.generate_one_time_password()
    person = service.create_person(
        employee_code=values["employee_code"],
        name=values["name"],
        phone=values["phone"],
        role=role,
        language=values["language"],
        password_hash=hash_password(password),
        actor=current_user,
    )
    session.commit()
    return render_template("people/one_time_password.html", person=person, password=password)


@bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@requires("people", "act")
def edit(user_id: int):
    person = _target_or_403(user_id)
    roles = service.assignable_roles(current_user)
    if request.method == "GET":
        return render_template("people/form.html", person=person, values={}, roles=roles, languages=LANGUAGES, statuses=STATUSES)

    values = _form_values()
    role = _chosen_role(values["role"])
    if not values["name"] or role is None or values["status"] not in STATUSES or values["language"] not in LANGUAGES:
        flash(_("people.error.required"), "error")
        return render_template("people/form.html", person=person, values=values, roles=roles, languages=LANGUAGES, statuses=STATUSES), 400

    before = service.person_snapshot(person)
    role_changed = role.id != person.role_template_id
    person.name = values["name"]
    person.phone = values["phone"] or None
    person.language = values["language"]
    person.role_template_id = role.id
    person.role = role
    if values["status"] != person.status:
        person.status = values["status"]
        if person.status != "active":
            person.session_epoch += 1
            tokens.revoke_user_tokens(person.id)
    audit.record("person.edit", "user", person.id, actor=current_user, before=before, after=service.person_snapshot(person))

    if role_changed and request.form.get("reset_permissions") == "1":
        before_perms = service.permission_snapshot(person)
        service.apply_template(person, role.code)
        audit.record(
            "permissions.reset_to_template",
            "user",
            person.id,
            actor=current_user,
            before=before_perms,
            after={"template": role.code, **service.permission_snapshot(person)},
        )
    session.commit()
    flash(_("people.saved"), "ok")
    return redirect(url_for("people.index"))


@bp.get("/<int:user_id>/permissions")
@requires("permissions")
def permissions(user_id: int):
    person = _target_or_403(user_id)
    screens = list(session.scalars(select(Screen).order_by(Screen.area.desc(), Screen.code)))
    return render_template("people/permissions.html", person=person, screens=screens)


@bp.post("/<int:user_id>/permissions")
@requires("permissions", "act")
def permissions_save(user_id: int):
    person = _target_or_403(user_id)
    requested = {
        s.code: {
            "view": request.form.get(f"view_{s.code}") == "1",
            "act": request.form.get(f"act_{s.code}") == "1",
        }
        for s in SCREENS
    }
    service.save_permissions(current_user, person, requested)
    session.commit()
    flash(_("people.saved"), "ok")
    return redirect(url_for("people.permissions", user_id=person.id))


@bp.post("/<int:user_id>/unlock")
@requires("people_unlock", "act")
def unlock_person(user_id: int):
    person = _target_or_403(user_id)
    unlock(person)
    audit.record("person.unlock", "user", person.id, actor=current_user)
    session.commit()
    flash(_("people.unlocked"), "ok")
    return redirect(url_for("people.index"))


@bp.post("/<int:user_id>/reset-device")
@requires("people_unlock", "act")
def reset_device(user_id: int):
    person = _target_or_403(user_id)
    device = tokens.active_device_of(person)
    if device is not None:
        before = {"install_id": device.install_id, "model": device.model}
        tokens.unbind_device(device, current_user)
        audit.record("device.reset", "user", person.id, actor=current_user, before=before)
        session.commit()
    flash(_("people.device_reset"), "ok")
    return redirect(url_for("people.index"))


@bp.post("/<int:user_id>/reset-password")
@requires("people", "act")
def reset_password(user_id: int):
    person = _target_or_403(user_id)
    password = service.generate_one_time_password()
    person.password_hash = hash_password(password)
    person.must_change_password = True
    person.session_epoch += 1
    tokens.revoke_user_tokens(person.id)
    audit.record("password.reset", "user", person.id, actor=current_user)
    session.commit()
    return render_template("people/one_time_password.html", person=person, password=password)
