"""Screens and role templates, defined in code and seeded into the database."""
from __future__ import annotations

from dataclasses import dataclass


def N_(key: str) -> str:
    """Marks a translation key for extraction; translated when it is shown."""
    return key


@dataclass(frozen=True)
class ScreenDef:
    code: str
    area: str  # web or app
    name_key: str


SCREENS = [
    ScreenDef("people", "web", N_("screen.people")),
    ScreenDef("people_unlock", "web", N_("screen.people_unlock")),
    ScreenDef("permissions", "web", N_("screen.permissions")),
    ScreenDef("groups", "web", N_("screen.groups")),
    ScreenDef("shifts", "web", N_("screen.shifts")),
    ScreenDef("schedule", "web", N_("screen.schedule")),
    ScreenDef("absences", "web", N_("screen.absences")),
    ScreenDef("lines", "web", N_("screen.lines")),
    ScreenDef("machine_types", "web", N_("screen.machine_types")),
    ScreenDef("machines", "web", N_("screen.machines")),
    ScreenDef("places", "web", N_("screen.places")),
    ScreenDef("settings", "web", N_("screen.settings")),
    ScreenDef("parts", "web", N_("screen.parts")),
    ScreenDef("part_requests", "web", N_("screen.part_requests")),
    ScreenDef("ticket_board", "web", N_("screen.ticket_board")),
    ScreenDef("app_raise", "app", N_("screen.app_raise")),
    ScreenDef("app_incharge", "app", N_("screen.app_incharge")),
    ScreenDef("app_technician", "app", N_("screen.app_technician")),
    ScreenDef("app_manager", "app", N_("screen.app_manager")),
]

_WEB_ALL = {s.code: "act" for s in SCREENS if s.area == "web"}

# role code -> (translation key, {screen code: "view" or "act"})
ROLE_TEMPLATES: dict[str, tuple[str, dict[str, str]]] = {
    "line_operator": (N_("role.line_operator"), {"app_raise": "act"}),
    "production_incharge": (N_("role.production_incharge"), {"app_raise": "act"}),
    "technician": (N_("role.technician"), {"app_technician": "act"}),
    "maintenance_incharge": (N_("role.maintenance_incharge"), {"app_incharge": "act", "app_technician": "act"}),
    "manager": (N_("role.manager"), {**_WEB_ALL, "app_manager": "act"}),
    "store": (N_("role.store"), {"parts": "act", "part_requests": "act"}),
    "viewer": (N_("role.viewer"), {"ticket_board": "view"}),
    "admin": (N_("role.admin"), {**_WEB_ALL}),
    "super_admin": (N_("role.super_admin"), {**_WEB_ALL, "app_manager": "act"}),
}

# Who may manage whom: strictly higher rank only, so nobody can raise themselves
# or a peer. Everyone not listed has rank 0.
ROLE_RANK = {"manager": 1, "admin": 2, "super_admin": 3}

# D-52: these roles sign in on the web with password + TOTP.
TOTP_ROLES = frozenset({"manager", "admin", "super_admin"})

LANGUAGES = ("en", "hi", "bn")
