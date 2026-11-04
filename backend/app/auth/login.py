"""Password check with lockout: one counter for web and mobile (D-54)."""
from __future__ import annotations

from typing import Callable

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import select

from .. import clock
from ..db import session
from ..people.models import User
from .models import LoginAttempt

MAX_FAILURES = 5

_hasher = PasswordHasher()
# Checked for unknown employee codes, so they take as long as known ones.
_DUMMY_HASH = _hasher.hash("avirat-no-such-account")


class LoginRefused(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def _log_attempt(employee_code: str, success: bool, reason: str | None, ip, install_id) -> None:
    session.add(
        LoginAttempt(
            employee_code=employee_code[:32],
            device_install_id=install_id,
            ip=ip,
            at=clock.now(),
            success=success,
            reason=reason,
        )
    )


def register_failure(user: User) -> bool:
    """Count one failure; lock at the fifth in a row. Returns True if now locked."""
    user.failed_logins += 1
    if user.failed_logins >= MAX_FAILURES and user.locked_at is None:
        user.locked_at = clock.now()
    return user.is_locked


def authenticate(
    employee_code: str,
    password: str,
    *,
    ip: str | None = None,
    install_id: str | None = None,
    precheck: Callable[[User], str | None] | None = None,
) -> User:
    """Return the user, or commit the attempt and raise LoginRefused.

    `precheck` runs before the password and isn't counted (D-54): a phone other than
    the bound one, or a web login on an account with no web screens.
    """

    def refuse(code: str):
        _log_attempt(employee_code, False, code, ip, install_id)
        session.commit()
        return LoginRefused(code)

    user = session.scalar(select(User).where(User.employee_code == employee_code).with_for_update())
    if user is None:
        verify_password(_DUMMY_HASH, password)
        raise refuse("invalid_credentials")

    if precheck is not None:
        code = precheck(user)
        if code:
            raise refuse(code)

    if user.is_locked:
        raise refuse("account_locked")

    correct = verify_password(user.password_hash, password)
    if not user.is_active:
        # Not counted: the account is already out of use.
        raise refuse("account_blocked" if correct else "invalid_credentials")

    if not correct:
        locked = register_failure(user)
        raise refuse("account_locked" if locked else "invalid_credentials")

    user.failed_logins = 0
    if _hasher.check_needs_rehash(user.password_hash):
        user.password_hash = _hasher.hash(password)
    _log_attempt(employee_code, True, None, ip, install_id)
    session.commit()
    return user


def unlock(user: User) -> None:
    user.locked_at = None
    user.failed_logins = 0
