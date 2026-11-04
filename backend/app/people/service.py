"""Rules for people and permissions. The caller commits."""
from __future__ import annotations

import secrets

from sqlalchemy import select

from .. import clock
from ..db import session
from . import audit
from .models import RoleTemplate, Screen, User, UserScreenPermission
from .registry import LANGUAGES, ROLE_RANK, ROLE_TEMPLATES, SCREENS, TOTP_ROLES

# D-55: no look-alike characters (0/O, 1/l/I).
ONE_TIME_ALPHABET = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ONE_TIME_LENGTH = 10
MIN_PASSWORD_WEB = 8
MIN_PASSWORD_PHONE = 6


def seed_registry() -> None:
    """Create or update screens and role templates from code. Never touches a person's permissions."""
    for screen in SCREENS:
        row = session.get(Screen, screen.code)
        if row is None:
            session.add(Screen(code=screen.code, area=screen.area, name_key=screen.name_key))
        else:
            row.area, row.name_key = screen.area, screen.name_key
    for code, (name_key, _perms) in ROLE_TEMPLATES.items():
        row = session.scalar(select(RoleTemplate).where(RoleTemplate.code == code))
        if row is None:
            session.add(RoleTemplate(code=code, name=name_key))
        else:
            row.name = name_key


def role_by_code(code: str) -> RoleTemplate | None:
    return session.scalar(select(RoleTemplate).where(RoleTemplate.code == code))


def all_roles() -> list[RoleTemplate]:
    return list(session.scalars(select(RoleTemplate).order_by(RoleTemplate.id)))


def rank(user: User) -> int:
    return ROLE_RANK.get(user.role.code, 0)


def role_rank(role_code: str) -> int:
    return ROLE_RANK.get(role_code, 0)


def can_manage(actor: User, target: User) -> bool:
    """Strictly higher rank only: the manager handles staff, an admin handles a manager,
    a Super Admin handles an admin. Unlocking a Super Admin is a server command (D-54)."""
    return actor.id != target.id and rank(actor) > rank(target)


def assignable_roles(actor: User) -> list[RoleTemplate]:
    return [r for r in all_roles() if role_rank(r.code) < rank(actor)]


def has_web_access(user: User) -> bool:
    return any(p.can_view and p.screen.area == "web" for p in user.permissions)


def requires_totp(user: User) -> bool:
    return user.role.code in TOTP_ROLES


def min_password_length(user: User) -> int:
    return MIN_PASSWORD_WEB if has_web_access(user) else MIN_PASSWORD_PHONE


def generate_one_time_password() -> str:
    return "".join(secrets.choice(ONE_TIME_ALPHABET) for _ in range(ONE_TIME_LENGTH))


def permission_snapshot(user: User) -> dict:
    return {p.screen_code: {"view": p.can_view, "act": p.can_act} for p in user.permissions}


def person_snapshot(user: User) -> dict:
    """What the audit log keeps about a person. Never the password hash."""
    return {
        "employee_code": user.employee_code,
        "name": user.name,
        "phone": user.phone,
        "role": user.role.code,
        "language": user.language,
        "status": user.status,
    }


def apply_template(user: User, role_code: str) -> None:
    """Copy a role template's permissions onto a person, replacing what they had."""
    _name, perms = ROLE_TEMPLATES[role_code]
    user.permissions.clear()
    session.flush()
    for screen_code, level in perms.items():
        user.permissions.append(
            UserScreenPermission(screen_code=screen_code, can_view=True, can_act=level == "act")
        )
    session.flush()
    # The screen relationship is needed straight after, for has_web_access.
    session.expire(user, ["permissions"])


def create_person(*, employee_code, name, phone, role: RoleTemplate, language, password_hash, actor) -> User:
    if language not in LANGUAGES:
        language = "en"
    user = User(
        employee_code=employee_code,
        name=name,
        phone=phone or None,
        role_template_id=role.id,
        language=language,
        password_hash=password_hash,
        must_change_password=True,
        created_at=clock.now(),
    )
    session.add(user)
    session.flush()
    session.refresh(user)
    apply_template(user, role.code)
    audit.record("person.create", "user", user.id, actor=actor, after=person_snapshot(user))
    return user


def save_permissions(actor: User, target: User, requested: dict[str, dict[str, bool]]) -> None:
    """Set a person's permissions. An actor can only give or take rights they hold
    themselves; other rights stay as they were, so nobody can raise anyone past their own level."""
    before = permission_snapshot(target)
    current = {p.screen_code: p for p in target.permissions}
    for screen_code in (s.code for s in SCREENS):
        wanted = requested.get(screen_code, {})
        existing = current.get(screen_code)
        view = existing.can_view if existing else False
        act = existing.can_act if existing else False
        if actor.can(screen_code, "view"):
            view = bool(wanted.get("view"))
        if actor.can(screen_code, "act"):
            act = bool(wanted.get("act"))
        view = view or act  # acting on a screen includes seeing it
        if existing is not None:
            existing.can_view, existing.can_act = view, act
        elif view or act:
            target.permissions.append(UserScreenPermission(screen_code=screen_code, can_view=view, can_act=act))
    session.flush()
    session.expire(target, ["permissions"])
    audit.record("permissions.change", "user", target.id, actor=actor, before=before, after=permission_snapshot(target))
