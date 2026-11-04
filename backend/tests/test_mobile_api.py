"""Phone login: device binding, tokens, lockout, my profile, device reset."""
from __future__ import annotations

import re

import pytest
from sqlalchemy import select

from app.auth.models import AccessToken, Device, LoginAttempt, RefreshToken
from app.auth.tokens import hash_token
from app.db import session as db
from app.people.models import AuditLog, User
from conftest import PASSWORD

PHONE_A = "install-aaaa"
PHONE_B = "install-bbbb"


def api_login(client, code="T1", password=PASSWORD, install_id=PHONE_A, **extra):
    return client.post(
        "/api/v1/auth/login",
        json={"employee_code": code, "password": password, "install_id": install_id, **extra},
    )


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def refresh(client, token, install_id=PHONE_A):
    return client.post("/api/v1/auth/refresh", json={"refresh_token": token, "install_id": install_id})


def code_of(response):
    return response.get_json()["error"]["code"]


def signed_in_tokens(client, make_user, code="T1"):
    make_user(code)
    return api_login(client, code).get_json()


# ---------------------------------------------------------------- login and binding


def test_first_login_binds_the_phone(make_user, client):
    make_user("T1")
    response = api_login(client, model="Redmi 12", os_version="14", app_version="1.0.0")
    assert response.status_code == 200
    body = response.get_json()
    assert body["token_type"] == "Bearer" and body["expires_in"] == 900
    assert body["user"]["device"]["install_id"] == PHONE_A
    device = db.scalar(select(Device))
    assert (device.install_id, device.model, device.active_user_id) == (PHONE_A, "Redmi 12", body["user"]["id"])


def test_same_phone_logs_in_again(make_user, client):
    make_user("T1")
    api_login(client)
    assert api_login(client).status_code == 200
    assert len(list(db.scalars(select(Device)))) == 1


def test_other_phone_is_refused_before_the_password_and_not_counted(make_user, client):
    person = make_user("T1")
    api_login(client)
    response = api_login(client, install_id=PHONE_B, password="wrong-password")
    assert response.status_code == 403 and code_of(response) == "device_mismatch"
    db.expire_all()
    assert db.get(User, person.id).failed_logins == 0
    assert db.scalars(select(LoginAttempt).order_by(LoginAttempt.id.desc())).first().reason == "device_mismatch"


def test_other_phone_never_locks_the_account(make_user, client):
    person = make_user("T1")
    api_login(client)
    for _ in range(8):
        api_login(client, install_id=PHONE_B, password="wrong-password")
    db.expire_all()
    assert not db.get(User, person.id).is_locked


def test_a_bound_phone_cannot_be_used_by_another_person(make_user, client):
    make_user("T1")
    make_user("T2")
    api_login(client, "T1")
    response = api_login(client, "T2")
    assert response.status_code == 403 and code_of(response) == "device_in_use"


def test_the_database_itself_allows_one_bound_phone_per_person(make_user, clock):
    from sqlalchemy.exc import IntegrityError

    person = make_user("T1")
    db.add(Device(user_id=person.id, install_id=PHONE_A, bound_at=clock.now()))
    db.commit()
    db.add(Device(user_id=person.id, install_id=PHONE_B, bound_at=clock.now()))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_wrong_password_and_unknown_person_look_the_same(make_user, client):
    make_user("T1")
    wrong = api_login(client, password="wrong-password")
    unknown = api_login(client, code="NOPE")
    assert wrong.status_code == unknown.status_code == 401
    assert code_of(wrong) == code_of(unknown) == "invalid_credentials"
    assert db.scalar(select(Device)) is None


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"employee_code": "T1", "password": PASSWORD},
        {"employee_code": "T1", "install_id": PHONE_A},
        {"employee_code": 5, "password": PASSWORD, "install_id": PHONE_A},
        {"employee_code": "T1", "password": PASSWORD, "install_id": "x" * 65},
    ],
)
def test_bad_login_body_is_a_400(make_user, client, body):
    make_user("T1")
    response = client.post("/api/v1/auth/login", json=body)
    assert response.status_code == 400 and code_of(response) == "bad_request"


def test_blocked_person_cannot_log_in(make_user, client):
    person = make_user("T1")
    person.status = "left"
    db.commit()
    assert code_of(api_login(client)) == "account_blocked"
    assert code_of(api_login(client, password="wrong-pass")) == "invalid_credentials"


# ---------------------------------------------------------------- lockout


def test_five_failures_lock_and_the_right_password_is_then_refused(make_user, client):
    make_user("T1")
    for _ in range(4):
        assert code_of(api_login(client, password="wrong-pass")) == "invalid_credentials"
    locked = api_login(client, password="wrong-pass")
    assert locked.status_code == 423 and code_of(locked) == "account_locked"
    assert code_of(api_login(client)) == "account_locked"


def test_web_and_phone_share_one_lockout_counter(make_user, client, app):
    person = make_user("S1", "store")
    for _ in range(3):
        api_login(client, "S1", password="wrong-pass")
    web = app.test_client()
    for _ in range(2):
        web.post("/login", data={"employee_code": "S1", "password": "wrong-pass"})
    db.expire_all()
    assert db.get(User, person.id).is_locked
    assert code_of(api_login(client, "S1")) == "account_locked"


def test_locking_stops_existing_tokens(make_user, client):
    body = signed_in_tokens(client, make_user)
    person = db.scalar(select(User))
    person.locked_at = person.created_at
    db.commit()
    assert client.get("/api/v1/me", headers=bearer(body["access_token"])).status_code == 401
    assert code_of(refresh(client, body["refresh_token"])) == "invalid_token"


# ---------------------------------------------------------------- tokens


def test_tokens_are_stored_only_as_hashes(make_user, client):
    body = signed_in_tokens(client, make_user)
    access = db.scalar(select(AccessToken))
    stored = db.scalar(select(RefreshToken))
    assert access.token_hash == hash_token(body["access_token"]) != body["access_token"]
    assert stored.token_hash == hash_token(body["refresh_token"]) != body["refresh_token"]


def test_access_token_lasts_15_minutes(make_user, client, clock):
    token = signed_in_tokens(client, make_user)["access_token"]
    clock.advance(minutes=14, seconds=59)
    assert client.get("/api/v1/me", headers=bearer(token)).status_code == 200
    clock.advance(seconds=1)
    assert client.get("/api/v1/me", headers=bearer(token)).status_code == 401


def test_refresh_token_lasts_90_days(make_user, client, clock):
    token = signed_in_tokens(client, make_user)["refresh_token"]
    clock.advance(days=90)
    assert code_of(refresh(client, token)) == "invalid_token"


def test_refresh_rotates(make_user, client):
    body = signed_in_tokens(client, make_user)
    response = refresh(client, body["refresh_token"])
    assert response.status_code == 200
    fresh = response.get_json()
    assert fresh["refresh_token"] != body["refresh_token"]
    assert client.get("/api/v1/me", headers=bearer(fresh["access_token"])).status_code == 200
    assert refresh(client, fresh["refresh_token"]).status_code == 200


def test_replaced_token_works_once_within_2_minutes(make_user, client, clock):
    """The reply to a refresh was lost on weak Wi-Fi; the phone retries with the old token."""
    old = signed_in_tokens(client, make_user)["refresh_token"]
    lost = refresh(client, old).get_json()
    clock.advance(seconds=119)
    retry = refresh(client, old)
    assert retry.status_code == 200
    fresh = retry.get_json()
    assert client.get("/api/v1/me", headers=bearer(fresh["access_token"])).status_code == 200
    assert refresh(client, fresh["refresh_token"]).status_code == 200
    # The replacement the phone never received no longer works.
    assert code_of(refresh(client, lost["refresh_token"])) == "invalid_token"


def test_second_reuse_within_2_minutes_revokes_the_device(make_user, client):
    old = signed_in_tokens(client, make_user)["refresh_token"]
    refresh(client, old)
    assert refresh(client, old).status_code == 200
    third = refresh(client, old)
    assert third.status_code == 401 and code_of(third) == "token_reused"


def test_reuse_after_2_minutes_revokes_every_token_of_the_device(make_user, client, clock):
    old = signed_in_tokens(client, make_user)["refresh_token"]
    fresh = refresh(client, old).get_json()
    clock.advance(seconds=121)
    response = refresh(client, old)
    assert response.status_code == 401 and code_of(response) == "token_reused"
    assert client.get("/api/v1/me", headers=bearer(fresh["access_token"])).status_code == 401
    assert code_of(refresh(client, fresh["refresh_token"])) == "invalid_token"


def test_refresh_from_another_phone_is_refused(make_user, client):
    token = signed_in_tokens(client, make_user)["refresh_token"]
    assert code_of(refresh(client, token, install_id=PHONE_B)) == "invalid_token"


def test_garbage_tokens_are_refused(client):
    assert code_of(refresh(client, "garbage")) == "invalid_token"
    assert client.get("/api/v1/me", headers=bearer("garbage")).status_code == 401
    assert client.get("/api/v1/me", headers={"Authorization": "Basic abc"}).status_code == 401


def test_logout_ends_tokens_but_the_phone_stays_bound(make_user, client):
    body = signed_in_tokens(client, make_user)
    assert client.post("/api/v1/auth/logout", headers=bearer(body["access_token"])).status_code == 200
    assert client.get("/api/v1/me", headers=bearer(body["access_token"])).status_code == 401
    assert code_of(refresh(client, body["refresh_token"])) == "invalid_token"
    assert db.scalar(select(Device)).unbound_at is None
    assert api_login(client).status_code == 200


# ---------------------------------------------------------------- first-login password change


def test_first_login_can_only_change_the_password(make_user, client):
    make_user("T1", must_change=True)
    body = api_login(client).get_json()
    assert body["must_change_password"] is True
    headers = bearer(body["access_token"])
    me = client.get("/api/v1/me", headers=headers)
    assert me.status_code == 403 and code_of(me) == "password_change_required"
    response = client.post(
        "/api/v1/auth/change-password", headers=headers, json={"current_password": PASSWORD, "new_password": "newpass"}
    )
    assert response.status_code == 200
    assert client.get("/api/v1/me", headers=headers).status_code == 200
    db.expire_all()
    assert not db.scalar(select(User)).must_change_password


def test_phone_only_password_needs_6_characters(make_user, client):
    make_user("T1", must_change=True)
    headers = bearer(api_login(client).get_json()["access_token"])
    short = client.post(
        "/api/v1/auth/change-password", headers=headers, json={"current_password": PASSWORD, "new_password": "12345"}
    )
    assert short.status_code == 400 and code_of(short) == "password_too_short"
    assert "6" in short.get_json()["error"]["message"]


def test_account_with_web_access_needs_8_characters_on_the_phone_too(make_user, client):
    make_user("S1", "store", must_change=True)
    headers = bearer(api_login(client, "S1").get_json()["access_token"])
    short = client.post(
        "/api/v1/auth/change-password", headers=headers, json={"current_password": PASSWORD, "new_password": "1234567"}
    )
    assert short.status_code == 400 and code_of(short) == "password_too_short"


def test_new_password_must_differ_and_wrong_current_counts(make_user, client):
    person = make_user("T1", must_change=True)
    headers = bearer(api_login(client).get_json()["access_token"])
    same = client.post(
        "/api/v1/auth/change-password", headers=headers, json={"current_password": PASSWORD, "new_password": PASSWORD}
    )
    assert code_of(same) == "password_same"
    for _ in range(5):
        wrong = client.post(
            "/api/v1/auth/change-password", headers=headers, json={"current_password": "wrong", "new_password": "newpass"}
        )
    assert wrong.status_code == 423
    db.expire_all()
    assert db.get(User, person.id).is_locked


# ---------------------------------------------------------------- my profile


def test_me_returns_the_profile_and_permissions(make_user, client):
    body = signed_in_tokens(client, make_user)
    response = client.get("/api/v1/me", headers=bearer(body["access_token"]))
    assert response.status_code == 200
    me = response.get_json()
    assert me["employee_code"] == "T1" and me["role"] == "technician" and me["language"] == "en"
    assert {"screen": "app_technician", "can_view": True, "can_act": True} in me["permissions"]
    assert me["device"]["install_id"] == PHONE_A
    assert "password_hash" not in me and "failed_logins" not in me


def test_language_per_person_changes_api_messages(make_user, client):
    body = signed_in_tokens(client, make_user)
    headers = bearer(body["access_token"])
    assert client.put("/api/v1/me/language", headers=headers, json={"language": "hi"}).status_code == 200
    bad = client.put("/api/v1/me/language", headers=headers, json={"language": "fr"})
    assert code_of(bad) == "invalid_language"
    assert bad.get_json()["error"]["message"] == "यह भाषा उपलब्ध नहीं है।"


def test_api_error_messages_follow_the_phone_language_before_login(make_user, client):
    make_user("T1")
    response = client.post(
        "/api/v1/auth/login",
        json={"employee_code": "T1", "password": "wrong-pass", "install_id": PHONE_A},
        headers={"Accept-Language": "bn"},
    )
    assert response.get_json()["error"]["message"] == "কর্মচারী আইডি বা পাসওয়ার্ড ভুল।"


# ---------------------------------------------------------------- manager reset


def test_manager_resets_the_device_and_the_next_phone_binds(make_user, client, web_login, app):
    body = signed_in_tokens(client, make_user)
    person = db.scalar(select(User))
    manager = make_user("M1", "manager")
    manager_client = app.test_client()
    web_login(manager_client, manager)
    assert manager_client.post(f"/people/{person.id}/reset-device").status_code == 302

    assert client.get("/api/v1/me", headers=bearer(body["access_token"])).status_code == 401
    assert code_of(refresh(client, body["refresh_token"])) == "invalid_token"
    assert api_login(client, install_id=PHONE_B).status_code == 200

    db.expire_all()
    devices = list(db.scalars(select(Device).order_by(Device.id)))
    assert len(devices) == 2
    assert devices[0].unbound_by == manager.id and devices[0].active_user_id is None
    assert devices[1].active_user_id == person.id
    assert db.scalar(select(AuditLog).where(AuditLog.action == "device.reset")).actor_user_id == manager.id


def test_a_reset_phone_can_be_bound_to_someone_else(make_user, client, web_login, app):
    signed_in_tokens(client, make_user)
    first = db.scalar(select(User))
    make_user("T2")
    manager_client = app.test_client()
    web_login(manager_client, make_user("M1", "manager"))
    manager_client.post(f"/people/{first.id}/reset-device")
    assert api_login(client, "T2", install_id=PHONE_A).status_code == 200


def test_password_reset_revokes_tokens_but_keeps_the_binding(make_user, client, web_login, app):
    body = signed_in_tokens(client, make_user)
    person = db.scalar(select(User))
    manager_client = app.test_client()
    web_login(manager_client, make_user("M1", "manager"))
    page = manager_client.post(f"/people/{person.id}/reset-password").get_data(as_text=True)
    new_password = re.search(r'class="otp"><code>([^<]+)</code>', page).group(1)
    assert client.get("/api/v1/me", headers=bearer(body["access_token"])).status_code == 401
    assert code_of(refresh(client, body["refresh_token"])) == "invalid_token"
    assert code_of(api_login(client, install_id=PHONE_B, password=new_password)) == "device_mismatch"
    assert api_login(client, password=new_password).get_json()["must_change_password"] is True


def test_blocking_a_person_revokes_tokens(make_user, client, web_login, app):
    body = signed_in_tokens(client, make_user)
    person = db.scalar(select(User))
    manager_client = app.test_client()
    web_login(manager_client, make_user("M1", "manager"))
    manager_client.post(
        f"/people/{person.id}/edit", data={"name": person.name, "role": "technician", "language": "en", "status": "blocked"}
    )
    assert client.get("/api/v1/me", headers=bearer(body["access_token"])).status_code == 401
    assert code_of(refresh(client, body["refresh_token"])) == "invalid_token"


def test_store_person_cannot_reset_a_device(make_user, client, web_login):
    target = make_user("T1")
    web_login(client, make_user("S1", "store"))
    assert client.post(f"/people/{target.id}/reset-device").status_code == 403
    assert client.post(f"/people/{target.id}/unlock").status_code == 403
