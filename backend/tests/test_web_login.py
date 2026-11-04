"""Web sign-in: password, first-login change, lockout, TOTP, recovery codes, CSRF."""
from __future__ import annotations

import re

import pyotp
from sqlalchemy import select

from app.auth import totp as totp_module
from app.auth.models import LoginAttempt, TotpRecoveryCode, TotpSecret
from app.db import session as db
from app.people.models import AuditLog, User
from conftest import PASSWORD


def login(client, code="S1", password=PASSWORD):
    return client.post("/login", data={"employee_code": code, "password": password})


def current_code(user_id, clock):
    secret = totp_module.decrypt_secret(db.get(TotpSecret, user_id).secret_encrypted)
    return pyotp.TOTP(secret).at(int(clock.now().timestamp()))


def enroll(client, clock):
    page = client.get("/totp/enroll").get_data(as_text=True)
    secret = re.search(r"<code>([A-Z2-7]+)</code>", page).group(1)
    return client.post("/totp/enroll", data={"code": pyotp.TOTP(secret).at(int(clock.now().timestamp()))})


def is_signed_in(client):
    return client.get("/profile").status_code == 200


# ---------------------------------------------------------------- password


def test_store_person_signs_in_with_password_only(make_user, client):
    make_user("S1", "store")
    response = login(client)
    assert response.status_code == 302 and response.headers["Location"].endswith("/")
    assert is_signed_in(client)


def test_wrong_password_is_refused_and_logged(make_user, client):
    make_user("S1", "store")
    response = login(client, password="wrong-password")
    assert response.status_code == 401
    assert not is_signed_in(client)
    attempt = db.scalar(select(LoginAttempt))
    assert (attempt.success, attempt.reason, attempt.employee_code) == (False, "invalid_credentials", "S1")


def test_unknown_employee_code_gets_the_same_answer_as_a_wrong_password(make_user, client):
    make_user("S1", "store")
    known = login(client, password="wrong-password")
    unknown = login(client, code="NOPE", password="wrong-password")
    assert known.status_code == unknown.status_code == 401
    assert "Wrong employee ID or password." in known.get_data(as_text=True)
    assert "Wrong employee ID or password." in unknown.get_data(as_text=True)


def test_signing_out_ends_the_session(make_user, client):
    make_user("S1", "store")
    login(client)
    client.post("/logout")
    assert not is_signed_in(client)


def test_blocked_account_cannot_sign_in_and_old_session_ends(make_user, client):
    person = make_user("S1", "store")
    login(client)
    person.status = "blocked"
    db.commit()
    assert not is_signed_in(client)
    other = client.application.test_client()
    assert login(other).status_code == 401
    assert "no longer active" in login(other).get_data(as_text=True)


def test_blocked_account_with_wrong_password_learns_nothing_and_is_not_counted(make_user, client):
    person = make_user("S1", "store")
    person.status = "left"
    db.commit()
    assert "Wrong employee ID" in login(client, password="wrong-one").get_data(as_text=True)
    db.expire_all()
    assert db.get(User, person.id).failed_logins == 0


# ---------------------------------------------------------------- no web screens


def test_account_with_no_web_screens_is_refused_before_the_password_check(make_user, client):
    person = make_user("T1", "technician")
    response = login(client, code="T1", password="wrong-password")
    assert response.status_code == 401
    assert "no web screens" in response.get_data(as_text=True)
    db.expire_all()
    assert db.get(User, person.id).failed_logins == 0


def test_no_web_screens_never_counts_towards_lockout(make_user, client):
    person = make_user("T1", "technician")
    for _ in range(7):
        login(client, code="T1", password="wrong-password")
    db.expire_all()
    assert not db.get(User, person.id).is_locked


# ---------------------------------------------------------------- lockout


def test_five_failures_lock_the_account(make_user, client):
    person = make_user("S1", "store")
    for attempt in range(4):
        assert "Wrong employee ID" in login(client, password="wrong-pass").get_data(as_text=True)
    assert "locked" in login(client, password="wrong-pass").get_data(as_text=True)
    db.expire_all()
    assert db.get(User, person.id).is_locked
    assert "locked" in login(client).get_data(as_text=True)  # even the right password
    assert not is_signed_in(client)


def test_a_success_resets_the_count(make_user, client):
    person = make_user("S1", "store")
    for _ in range(4):
        login(client, password="wrong-pass")
    login(client)
    client.post("/logout")
    db.expire_all()
    assert db.get(User, person.id).failed_logins == 0
    for _ in range(4):
        login(client, password="wrong-pass")
    db.expire_all()
    assert not db.get(User, person.id).is_locked


def test_failures_after_a_lock_do_not_keep_counting(make_user, client):
    person = make_user("S1", "store")
    for _ in range(8):
        login(client, password="wrong-pass")
    db.expire_all()
    assert db.get(User, person.id).failed_logins == 5


def test_manager_unlocks_and_it_is_audited(make_user, client, web_login, app):
    person = make_user("S1", "store")
    other = app.test_client()
    for _ in range(5):
        login(other, password="wrong-pass")
    manager = make_user("M1", "manager")
    web_login(client, manager)
    assert client.post(f"/people/{person.id}/unlock").status_code == 302
    db.expire_all()
    person = db.get(User, person.id)
    assert not person.is_locked and person.failed_logins == 0
    row = db.scalar(select(AuditLog).where(AuditLog.action == "person.unlock"))
    assert row.actor_user_id == manager.id
    assert login(other).status_code == 302


def test_manager_cannot_unlock_a_manager_but_an_admin_can(make_user, client, web_login, app):
    locked_manager = make_user("M2", "manager")
    locked_manager.locked_at = locked_manager.created_at
    db.commit()
    web_login(client, make_user("M1", "manager"))
    assert client.post(f"/people/{locked_manager.id}/unlock").status_code == 403
    admin_client = app.test_client()
    web_login(admin_client, make_user("A1", "admin"))
    assert admin_client.post(f"/people/{locked_manager.id}/unlock").status_code == 302


def test_super_admin_unlock_is_a_server_command_only(make_user, client, web_login, app):
    target = make_user("SA2", "super_admin")
    target.locked_at = target.created_at
    db.commit()
    web_login(client, make_user("SA1", "super_admin"))
    assert client.post(f"/people/{target.id}/unlock").status_code == 403
    result = app.test_cli_runner().invoke(args=["users", "unlock", "SA2"])
    assert result.exit_code == 0, result.output
    db.expire_all()
    assert not db.get(User, target.id).is_locked
    assert db.scalar(select(AuditLog).where(AuditLog.action == "person.unlock")).actor_user_id is None


# ---------------------------------------------------------------- first login


def test_first_login_forces_a_password_change(make_user, client):
    person = make_user("S1", "store", must_change=True)
    response = login(client)
    assert response.headers["Location"].endswith("/change-password")
    assert not is_signed_in(client)
    response = client.post(
        "/change-password",
        data={"current_password": PASSWORD, "new_password": "brand-new-1", "confirm_password": "brand-new-1"},
    )
    assert response.status_code == 302
    assert is_signed_in(client)
    db.expire_all()
    assert not db.get(User, person.id).must_change_password


def test_password_rules_on_the_web(make_user, client):
    make_user("S1", "store", must_change=True)
    login(client)

    def change(current, new, confirm=None):
        return client.post(
            "/change-password",
            data={"current_password": current, "new_password": new, "confirm_password": confirm or new},
        )

    assert change(PASSWORD, "short7c").status_code == 400  # 8+ with web access
    assert change(PASSWORD, "long-enough", "different-one").status_code == 400
    assert change(PASSWORD, PASSWORD).status_code == 400
    assert change("wrong-current", "long-enough").status_code == 400
    assert change(PASSWORD, "long-enough").status_code == 302


def test_wrong_current_password_counts_towards_lockout(make_user, client):
    person = make_user("S1", "store", must_change=True)
    login(client)
    for _ in range(5):
        response = client.post(
            "/change-password",
            data={"current_password": "wrong", "new_password": "long-enough", "confirm_password": "long-enough"},
        )
    assert response.headers["Location"].endswith("/login")
    db.expire_all()
    assert db.get(User, person.id).is_locked


def test_signed_in_person_changes_their_password_and_stays_signed_in(make_user, client, app):
    person = make_user("S1", "store")
    login(client)
    other_browser = app.test_client()
    login(other_browser)
    response = client.post(
        "/change-password",
        data={"current_password": PASSWORD, "new_password": "brand-new-1", "confirm_password": "brand-new-1"},
    )
    assert response.status_code == 302 and response.headers["Location"].endswith("/")
    assert is_signed_in(client)
    assert not is_signed_in(other_browser)
    db.expire_all()
    assert db.get(User, person.id).session_epoch == 1
    client.post("/logout")
    assert login(client, password=PASSWORD).status_code == 401
    assert login(client, password="brand-new-1").status_code == 302


def test_changing_the_password_on_the_web_signs_the_phone_out(make_user, client, app):
    make_user("S1", "store")
    phone = app.test_client()
    token = phone.post(
        "/api/v1/auth/login", json={"employee_code": "S1", "password": PASSWORD, "install_id": "phone-1"}
    ).get_json()["access_token"]
    login(client)
    client.post(
        "/change-password",
        data={"current_password": PASSWORD, "new_password": "brand-new-1", "confirm_password": "brand-new-1"},
    )
    assert phone.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_change_password_page_is_reachable_while_signed_in(make_user, client):
    make_user("S1", "store")
    login(client)
    assert client.get("/change-password").status_code == 200


def test_change_password_needs_a_pending_or_signed_in_person(client):
    assert client.get("/change-password").headers["Location"].endswith("/login")


def test_pending_login_expires(make_user, client, clock):
    make_user("S1", "store", must_change=True)
    login(client)
    clock.advance(minutes=11)
    assert client.get("/change-password").headers["Location"].endswith("/login")


def test_password_reset_shows_a_new_one_time_password_and_ends_sessions(make_user, client, web_login, app):
    person = make_user("S1", "store")
    person_client = app.test_client()
    login(person_client)
    assert is_signed_in(person_client)
    web_login(client, make_user("M1", "manager"))
    page = client.post(f"/people/{person.id}/reset-password").get_data(as_text=True)
    password = re.search(r'class="otp"><code>([^<]+)</code>', page).group(1)
    assert not is_signed_in(person_client)
    assert login(person_client, password=PASSWORD).status_code == 401
    assert login(person_client, password=password).headers["Location"].endswith("/change-password")


# ---------------------------------------------------------------- TOTP


def test_manager_must_enroll_totp_and_gets_recovery_codes_once(make_user, client, clock):
    person = make_user("M1", "manager")
    assert login(client, "M1").headers["Location"].endswith("/totp/enroll")
    assert not is_signed_in(client)
    response = enroll(client, clock)
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    codes = re.findall(r"<code>([a-z2-9]{5}-[a-z2-9]{5})</code>", page)
    assert len(codes) == 10
    assert is_signed_in(client)
    stored = list(db.scalars(select(TotpRecoveryCode).where(TotpRecoveryCode.user_id == person.id)))
    assert len(stored) == 10
    assert all(code not in [s.code_hash for s in stored] for code in codes)
    row = db.get(TotpSecret, person.id)
    assert totp_module.decrypt_secret(row.secret_encrypted) != row.secret_encrypted


def test_all_three_roles_need_totp_and_others_do_not(make_user, app):
    for role in ("manager", "admin", "super_admin"):
        client = app.test_client()
        make_user(f"U{role}", role)
        assert login(client, f"U{role}").headers["Location"].endswith("/totp/enroll"), role
    client = app.test_client()
    make_user("V1", "viewer")
    assert login(client, "V1").headers["Location"].endswith("/")


def test_wrong_code_at_enrollment_does_not_enroll(make_user, client):
    person = make_user("M1", "manager")
    login(client, "M1")
    client.get("/totp/enroll")
    client.post("/totp/enroll", data={"code": "000000"})
    assert db.get(TotpSecret, person.id) is None
    assert not is_signed_in(client)


def enrolled_manager(make_user, app, clock, code="M1"):
    person = make_user(code, "manager")
    first = app.test_client()
    login(first, code)
    enroll(first, clock)
    clock.advance(seconds=120)
    return person


def test_second_sign_in_asks_for_a_code(make_user, client, app, clock):
    person = enrolled_manager(make_user, app, clock)
    assert login(client, "M1").headers["Location"].endswith("/totp/verify")
    assert not is_signed_in(client)
    assert client.get("/people/").status_code == 302  # password alone opens nothing
    response = client.post("/totp/verify", data={"code": current_code(person.id, clock)})
    assert response.status_code == 302
    assert is_signed_in(client)


def test_a_code_works_only_once(make_user, client, app, clock):
    person = enrolled_manager(make_user, app, clock)
    code = current_code(person.id, clock)
    login(client, "M1")
    client.post("/totp/verify", data={"code": code})
    client.post("/logout")
    login(client, "M1")
    assert client.post("/totp/verify", data={"code": code}).status_code == 401
    assert not is_signed_in(client)


def test_a_code_from_the_clock_drift_window_works_but_an_old_one_does_not(make_user, client, app, clock):
    person = enrolled_manager(make_user, app, clock)
    code = current_code(person.id, clock)
    clock.advance(seconds=30)
    login(client, "M1")
    assert client.post("/totp/verify", data={"code": code}).status_code == 302
    client.post("/logout")
    code = current_code(person.id, clock)
    clock.advance(seconds=120)
    login(client, "M1")
    assert client.post("/totp/verify", data={"code": code}).status_code == 401


def test_wrong_codes_count_towards_the_same_lockout(make_user, client, app, clock):
    person = enrolled_manager(make_user, app, clock)
    login(client, "M1")
    for _ in range(5):
        response = client.post("/totp/verify", data={"code": "000000"})
    assert response.headers["Location"].endswith("/login")
    db.expire_all()
    assert db.get(User, person.id).is_locked


def test_recovery_code_signs_in_once(make_user, client, app, clock):
    person = make_user("M1", "manager")
    first = app.test_client()
    login(first, "M1")
    codes = re.findall(r"<code>([a-z2-9]{5}-[a-z2-9]{5})</code>", enroll(first, clock).get_data(as_text=True))
    login(client, "M1")
    assert client.post("/totp/verify", data={"code": codes[0]}).status_code == 302
    client.post("/logout")
    login(client, "M1")
    assert client.post("/totp/verify", data={"code": codes[0]}).status_code == 401
    assert client.post("/totp/verify", data={"code": codes[1].upper()}).status_code == 302


def test_totp_steps_refuse_a_person_who_is_not_pending(client):
    assert client.get("/totp/verify").headers["Location"].endswith("/login")
    assert client.get("/totp/enroll").headers["Location"].endswith("/login")


def test_first_login_changes_the_password_before_totp(make_user, client):
    make_user("M1", "manager", must_change=True)
    assert login(client, "M1").headers["Location"].endswith("/change-password")
    assert client.get("/totp/enroll").headers["Location"].endswith("/login")
    response = client.post(
        "/change-password",
        data={"current_password": PASSWORD, "new_password": "long-enough", "confirm_password": "long-enough"},
    )
    assert response.headers["Location"].endswith("/totp/enroll")


def test_reset_totp_command_makes_the_person_enroll_again(make_user, client, app, clock):
    person = enrolled_manager(make_user, app, clock)
    result = app.test_cli_runner().invoke(args=["users", "reset-totp", "M1"])
    assert result.exit_code == 0, result.output
    db.expire_all()
    assert db.get(TotpSecret, person.id) is None
    assert list(db.scalars(select(TotpRecoveryCode))) == []
    assert login(client, "M1").headers["Location"].endswith("/totp/enroll")


# ---------------------------------------------------------------- CSRF and language


def test_web_forms_need_a_csrf_token(make_user, app):
    make_user("S1", "store")
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()
    assert client.post("/login", data={"employee_code": "S1", "password": PASSWORD}).status_code == 400
    page = client.get("/login").get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    response = client.post("/login", data={"employee_code": "S1", "password": PASSWORD, "csrf_token": token})
    assert response.status_code == 302
    assert client.post("/logout").status_code == 400


def test_session_cookie_settings(app):
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"


def test_person_language_is_used_after_sign_in(make_user, client):
    make_user("S1", "store", language="bn")
    login(client)
    assert "আমার প্রোফাইল" in client.get("/profile").get_data(as_text=True)


def test_person_can_change_their_language(make_user, client):
    person = make_user("S1", "store")
    login(client)
    client.post("/profile", data={"language": "hi"})
    assert "मेरी प्रोफ़ाइल" in client.get("/profile").get_data(as_text=True)
    db.expire_all()
    assert db.get(User, person.id).language == "hi"
    client.post("/profile", data={"language": "fr"})
    db.expire_all()
    assert db.get(User, person.id).language == "hi"


def test_language_choice_on_the_sign_in_page(client):
    client.post("/language", data={"language": "bn"})
    assert "সাইন ইন" in client.get("/login").get_data(as_text=True)
