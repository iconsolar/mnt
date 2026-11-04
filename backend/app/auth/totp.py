"""TOTP and one-time recovery codes for Super Admin, Admin and Manager (D-52)."""
from __future__ import annotations

import hashlib
import secrets

import pyotp
import segno
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from sqlalchemy import select

from .. import clock
from ..db import session
from ..people.models import User
from .models import TotpRecoveryCode, TotpSecret

ISSUER = "Avirat"
STEP_SECONDS = 30
RECOVERY_CODE_COUNT = 10
_RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def _fernet() -> Fernet:
    return Fernet(current_app.config["AVIRAT"].totp_key.encode())


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None


def new_secret() -> str:
    return pyotp.random_base32()


def is_enrolled(user: User) -> bool:
    return session.get(TotpSecret, user.id) is not None


def provisioning_qr(secret: str, user: User) -> str:
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.employee_code, issuer_name=ISSUER)
    return segno.make(uri, error="m").svg_data_uri(scale=5)


def _matching_step(secret: str, code: str) -> int | None:
    totp = pyotp.TOTP(secret)
    code = code.strip().replace(" ", "")
    step = int(clock.now().timestamp()) // STEP_SECONDS
    for candidate in (step, step - 1, step + 1):  # one step either way, for phone clock drift
        if secrets.compare_digest(totp.at(candidate * STEP_SECONDS), code):
            return candidate
    return None


def code_matches_secret(secret: str, code: str) -> bool:
    return _matching_step(secret, code) is not None


def _generate_recovery_code() -> str:
    raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(10))
    return f"{raw[:5]}-{raw[5:]}"


def _hash_recovery(code: str) -> str:
    return hashlib.sha256(code.strip().lower().replace("-", "").encode()).hexdigest()


def complete_enrollment(user: User, secret: str) -> list[str]:
    """Save the secret and return the recovery codes. They are shown once and only hashes stay."""
    now = clock.now()
    session.add(TotpSecret(user_id=user.id, secret_encrypted=encrypt_secret(secret), enrolled_at=now))
    codes = [_generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    for code in codes:
        session.add(TotpRecoveryCode(user_id=user.id, code_hash=_hash_recovery(code), created_at=now))
    return codes


def verify_code(user: User, code: str) -> bool:
    """A current TOTP code (each usable once) or an unused recovery code."""
    row = session.scalar(select(TotpSecret).where(TotpSecret.user_id == user.id).with_for_update())
    if row is None:
        return False
    secret = decrypt_secret(row.secret_encrypted)
    if secret is not None:
        step = _matching_step(secret, code)
        if step is not None and (row.last_used_step is None or step > row.last_used_step):
            row.last_used_step = step
            return True
    recovery = session.scalar(
        select(TotpRecoveryCode)
        .where(
            TotpRecoveryCode.user_id == user.id,
            TotpRecoveryCode.code_hash == _hash_recovery(code),
            TotpRecoveryCode.used_at.is_(None),
        )
        .with_for_update()
    )
    if recovery is not None:
        recovery.used_at = clock.now()
        return True
    return False


def reset(user: User) -> None:
    """Server command only: drop TOTP so the person enrolls again at next sign-in."""
    row = session.get(TotpSecret, user.id)
    if row is not None:
        session.delete(row)
    for code in session.scalars(select(TotpRecoveryCode).where(TotpRecoveryCode.user_id == user.id)):
        session.delete(code)
