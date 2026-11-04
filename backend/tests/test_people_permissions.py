"""Routes, permissions, role templates, audit log, and the rank rule."""
from __future__ import annotations

import re

from click.testing import CliRunner
from sqlalchemy import select

from app.auth.login import verify_password
from app.db import session as db
from app.people import audit, service
from app.people.access import PUBLIC_ENDPOINTS, rule_of
from app.people.models import AuditLog, User
from app.people.registry import ROLE_TEMPLATES, SCREENS


def audit_rows(action=None):
    db.expire_all()
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    return list(db.scalars(stmt))


# ---------------------------------------------------------------- every route


def test_every_route_has_a_rule_or_is_on_the_public_list(app):
    offenders = []
    for endpoint, view in app.view_functions.items():
        if endpoint not in PUBLIC_ENDPOINTS and rule_of(view) is None:
            offenders.append(endpoint)
    assert offenders == []


def test_the_public_list_has_no_stale_names_and_no_rules(app):
    for endpoint in PUBLIC_ENDPOINTS:
        assert endpoint in app.view_functions, endpoint
        assert rule_of(app.view_functions[endpoint]) is None, endpoint


def test_every_rule_names_a_real_screen(app):
    codes = {s.code for s in SCREENS}
    for view in app.view_functions.values():
        rule = rule_of(view)
        if rule is not None and rule.screen is not None:
            assert rule.screen in codes


def test_a_route_without_a_rule_is_refused(app, client):
    """Fail closed: forgetting the rule gives a 403, not an open page."""
    app.view_functions["people.index"], original = (lambda: "open"), app.view_functions["people.index"]
    try:
        assert client.get("/people/").status_code == 403
    finally:
        app.view_functions["people.index"] = original


def test_web_pages_redirect_to_login_when_signed_out(client):
    response = client.get("/people/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_api_refuses_without_a_token(client):
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------- permissions


def test_role_template_is_copied_when_the_person_is_created(make_user):
    technician = make_user(role="technician")
    assert technician.can("app_technician", "act")
    assert not technician.can("people")


def test_permissions_can_differ_from_the_template_for_one_person(make_user, client, web_login):
    admin = make_user("A1", "admin")
    tech = make_user("T1", "technician")
    web_login(client, admin)
    response = client.post(f"/people/{tech.id}/permissions", data={"view_parts": "1", "act_app_technician": "1"})
    assert response.status_code == 302
    db.expire_all()
    tech = db.get(User, tech.id)
    assert tech.can("parts", "view")
    assert not tech.can("parts", "act")
    assert tech.can("app_technician", "act")
    other = make_user("T2", "technician")
    assert not other.can("parts")


def test_view_permission_is_not_enough_to_change(make_user, client, web_login):
    store = make_user("S1", "store")
    service.save_permissions(store, store, {})  # no-op: store holds no people rights
    db.commit()
    viewer = make_user("V1", "viewer")
    admin = make_user("A1", "admin")
    web_login(client, admin)
    client.post(f"/people/{viewer.id}/permissions", data={"view_people": "1", "view_ticket_board": "1"})
    client2 = client.application.test_client()
    db.expire_all()
    viewer = db.get(User, viewer.id)
    web_login(client2, viewer)
    assert client2.get("/people/").status_code == 200
    assert client2.get("/people/new").status_code == 403
    assert client2.post("/people/new", data={}).status_code == 403


def test_denied_page_is_closed_not_just_hidden(make_user, client, web_login):
    store = make_user("S1", "store")
    web_login(client, store)
    assert client.get("/people/").status_code == 403


def test_act_includes_view(make_user):
    admin = make_user("A1", "admin")
    tech = make_user("T1", "technician")
    service.save_permissions(admin, tech, {"parts": {"act": True}})
    db.commit()
    db.expire_all()
    tech = db.get(User, tech.id)
    assert tech.can("parts", "view") and tech.can("parts", "act")


def test_nobody_can_give_a_right_they_do_not_hold(make_user):
    manager = make_user("M1", "manager")
    tech = make_user("T1", "technician")
    # Take a right away from the manager, then try to give it.
    service.save_permissions(make_user("SA", "super_admin"), manager, {s.code: {} for s in SCREENS})
    db.commit()
    db.expire_all()
    manager = db.get(User, manager.id)
    assert not manager.can("settings", "act")
    service.save_permissions(manager, tech, {"settings": {"act": True, "view": True}})
    db.commit()
    db.expire_all()
    assert not db.get(User, tech.id).can("settings")


def test_a_right_the_actor_lacks_is_left_alone_not_removed(make_user):
    target = make_user("T1", "technician")  # holds app_technician
    actor = make_user("A1", "admin")  # admin's template has web screens only
    assert not actor.can("app_technician", "act")
    service.save_permissions(actor, target, {})
    db.commit()
    db.expire_all()
    assert db.get(User, target.id).can("app_technician", "act")


# ---------------------------------------------------------------- rank rule


def test_rank_rule(make_user):
    sa = make_user("SA", "super_admin")
    admin = make_user("A1", "admin")
    manager = make_user("M1", "manager")
    tech = make_user("T1", "technician")
    assert service.can_manage(manager, tech)
    assert service.can_manage(admin, manager)
    assert service.can_manage(sa, admin)
    assert not service.can_manage(manager, admin)
    assert not service.can_manage(manager, make_user("M2", "manager"))
    assert not service.can_manage(admin, sa)
    assert not service.can_manage(sa, make_user("SA2", "super_admin"))  # a server command
    assert not service.can_manage(manager, manager)


def test_manager_cannot_edit_an_admin_or_themselves(make_user, client, web_login):
    manager = make_user("M1", "manager")
    admin = make_user("A1", "admin")
    web_login(client, manager)
    assert client.get(f"/people/{admin.id}/edit").status_code == 403
    assert client.post(f"/people/{admin.id}/reset-password").status_code == 403
    assert client.get(f"/people/{manager.id}/permissions").status_code == 403


def test_manager_cannot_create_a_role_above_their_own(make_user, client, web_login):
    web_login(client, make_user("M1", "manager"))
    response = client.post("/people/new", data={"employee_code": "X1", "name": "X", "role": "admin"})
    assert response.status_code == 400
    assert db.scalar(select(User).where(User.employee_code == "X1")) is None


# ---------------------------------------------------------------- people screens


def test_create_person_shows_a_one_time_password_once_and_stores_only_a_hash(make_user, client, web_login):
    web_login(client, make_user("M1", "manager"))
    response = client.post(
        "/people/new", data={"employee_code": "T9", "name": "New Tech", "role": "technician", "language": "hi"}
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    password = re.search(r'class="otp"><code>([^<]+)</code>', page).group(1)
    assert not set("0O1lI") & set(password)
    db.expire_all()
    person = db.scalar(select(User).where(User.employee_code == "T9"))
    assert person.must_change_password and person.language == "hi"
    assert password not in person.password_hash
    assert verify_password(person.password_hash, password)
    assert person.can("app_technician", "act")
    assert password not in str([(a.before_json, a.after_json) for a in audit_rows()])
    assert "password_hash" not in str(audit_rows("person.create")[0].after_json)


def test_duplicate_employee_code_is_refused(make_user, client, web_login):
    web_login(client, make_user("M1", "manager"))
    make_user("T1")
    response = client.post("/people/new", data={"employee_code": "T1", "name": "Other", "role": "technician"})
    assert response.status_code == 400


def test_people_search(make_user, client, web_login):
    web_login(client, make_user("M1", "manager"))
    make_user("T1", name="Asha Devi")
    make_user("T2", name="Ravi Kumar")
    page = client.get("/people/?q=asha").get_data(as_text=True)
    assert "Asha Devi" in page and "Ravi Kumar" not in page


def test_role_change_keeps_permissions_unless_reset_is_chosen(make_user, client, web_login):
    web_login(client, make_user("M1", "manager"))
    person = make_user("T1", "technician")
    form = {"name": person.name, "role": "store", "language": "en", "status": "active"}

    client.post(f"/people/{person.id}/edit", data=form)
    db.expire_all()
    person = db.get(User, person.id)
    assert person.role.code == "store"
    assert person.can("app_technician", "act") and not person.can("parts")
    assert audit_rows("permissions.reset_to_template") == []

    form["role"] = "viewer"
    client.post(f"/people/{person.id}/edit", data={**form, "reset_permissions": "1"})
    db.expire_all()
    person = db.get(User, person.id)
    assert person.can("ticket_board") and not person.can("app_technician")
    rows = audit_rows("permissions.reset_to_template")
    assert len(rows) == 1
    assert rows[0].after_json["template"] == "viewer"


# ---------------------------------------------------------------- audit


def test_person_change_writes_who_before_and_after(make_user, client, web_login):
    manager = make_user("M1", "manager")
    web_login(client, manager)
    person = make_user("T1", "technician", name="Old Name")
    client.post(
        f"/people/{person.id}/edit",
        data={"name": "New Name", "role": "technician", "language": "en", "status": "active"},
    )
    row = audit_rows("person.edit")[0]
    assert row.actor_user_id == manager.id
    assert row.before_json["name"] == "Old Name"
    assert row.after_json["name"] == "New Name"


def test_audit_row_and_change_share_one_transaction(make_user, clock):
    person = make_user("T1")
    person.name = "Changed"
    audit.record("person.edit", "user", person.id, actor=None, after={"name": "Changed"})
    db.flush()
    db.rollback()
    db.expire_all()
    assert db.get(User, person.id).name == f"Person T1"
    assert audit_rows("person.edit") == []


def test_audit_time_comes_from_the_clock(make_user, clock):
    person = make_user("T1")
    clock.advance(hours=3)
    audit.record("x.y", "user", person.id)
    db.commit()
    assert audit_rows("x.y")[0].at == clock.now()


def test_permission_change_is_audited(make_user, client, web_login):
    admin = make_user("A1", "admin")
    tech = make_user("T1", "technician")
    web_login(client, admin)
    client.post(f"/people/{tech.id}/permissions", data={"view_parts": "1", "act_app_technician": "1"})
    row = audit_rows("permissions.change")[0]
    assert row.actor_user_id == admin.id
    assert "parts" not in row.before_json
    assert row.after_json["parts"] == {"view": True, "act": False}


# ---------------------------------------------------------------- password rule and templates


def test_password_minimum_depends_on_web_access(make_user):
    assert service.min_password_length(make_user("T1", "technician")) == 6
    assert service.min_password_length(make_user("S1", "store")) == 8


def test_one_time_passwords_have_no_look_alikes():
    for _ in range(200):
        assert not set("0O1lI") & set(service.generate_one_time_password())


def test_seed_is_safe_to_run_twice_and_keeps_permissions(make_user):
    person = make_user("T1", "technician")
    service.seed_registry()
    db.commit()
    db.expire_all()
    assert db.get(User, person.id).can("app_technician", "act")


def test_every_template_names_real_screens():
    codes = {s.code for s in SCREENS}
    for _name, perms in ROLE_TEMPLATES.values():
        assert set(perms) <= codes


# ---------------------------------------------------------------- server commands


def test_create_superadmin_command(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["users", "create-superadmin", "SA1", "--name", "Mukesh"])
    assert result.exit_code == 0, result.output
    password = re.search(r"One-time password for SA1: (\S+)", result.output).group(1)
    db.expire_all()
    user = db.scalar(select(User).where(User.employee_code == "SA1"))
    assert user.role.code == "super_admin" and user.must_change_password
    assert verify_password(user.password_hash, password)
    assert runner.invoke(args=["users", "create-superadmin", "SA1"]).exit_code != 0
