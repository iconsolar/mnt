"""Phone tokens: opaque, stored as hashes, rotated on refresh (D-53)."""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta

from flask import g, request
from sqlalchemy import select, update

from .. import clock
from ..db import session
from ..people.models import User
from .models import AccessToken, Device, RefreshToken

ACCESS_TTL = timedelta(minutes=15)
REFRESH_TTL = timedelta(days=90)
REFRESH_GRACE = timedelta(minutes=2)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_row: RefreshToken


class TokenRefused(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def active_device_of(user: User) -> Device | None:
    return session.scalar(select(Device).where(Device.user_id == user.id, Device.unbound_at.is_(None)))


def active_device_by_install(install_id: str) -> Device | None:
    return session.scalar(select(Device).where(Device.install_id == install_id, Device.unbound_at.is_(None)))


def bind_device(user: User, install_id: str, *, model=None, os_version=None, app_version=None) -> Device:
    device = Device(
        user_id=user.id,
        install_id=install_id,
        model=model,
        os_version=os_version,
        app_version=app_version,
        bound_at=clock.now(),
        last_seen_at=clock.now(),
    )
    session.add(device)
    session.flush()
    return device


def issue_pair(user: User, device: Device) -> TokenPair:
    now = clock.now()
    access_raw = secrets.token_urlsafe(32)
    refresh_raw = secrets.token_urlsafe(48)
    session.add(
        AccessToken(
            user_id=user.id,
            device_id=device.id,
            token_hash=hash_token(access_raw),
            issued_at=now,
            expires_at=now + ACCESS_TTL,
        )
    )
    refresh_row = RefreshToken(
        user_id=user.id,
        device_id=device.id,
        token_hash=hash_token(refresh_raw),
        issued_at=now,
        expires_at=now + REFRESH_TTL,
    )
    session.add(refresh_row)
    session.flush()
    return TokenPair(access_raw, refresh_raw, int(ACCESS_TTL.total_seconds()), refresh_row)


def revoke_device_tokens(device_id: int) -> None:
    now = clock.now()
    session.execute(
        update(AccessToken).where(AccessToken.device_id == device_id, AccessToken.revoked_at.is_(None)).values(revoked_at=now)
    )
    session.execute(
        update(RefreshToken).where(RefreshToken.device_id == device_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=now)
    )


def revoke_user_tokens(user_id: int) -> None:
    now = clock.now()
    session.execute(
        update(AccessToken).where(AccessToken.user_id == user_id, AccessToken.revoked_at.is_(None)).values(revoked_at=now)
    )
    session.execute(
        update(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=now)
    )


def unbind_device(device: Device, actor: User | None) -> None:
    device.unbound_at = clock.now()
    device.unbound_by = actor.id if actor is not None else None
    revoke_device_tokens(device.id)


def refresh(raw: str, install_id: str | None) -> tuple[User, Device, TokenPair]:
    """Rotate a refresh token. Raises TokenRefused after saving any revocation it made."""
    now = clock.now()
    row = session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)).with_for_update()
    )
    if row is None or row.revoked_at is not None or row.expires_at <= now:
        raise TokenRefused("invalid_token")

    device = row.device
    user = row.user
    if device.unbound_at is not None or device.install_id != install_id or not user.is_active or user.is_locked:
        raise TokenRefused("invalid_token")

    if row.replaced_at is not None:
        within_grace = now - row.replaced_at <= REFRESH_GRACE
        if not within_grace or row.grace_used_at is not None:
            # Replaced and used again: someone may have copied it. Stop the whole device.
            revoke_device_tokens(device.id)
            session.commit()
            raise TokenRefused("token_reused")
        # The reply to the first refresh was probably lost, so the phone never saw the
        # replacement. Retire it and issue another, once.
        row.grace_used_at = now
        previous = session.get(RefreshToken, row.replaced_by_id)
        if previous is not None and previous.revoked_at is None:
            previous.revoked_at = now
    else:
        row.replaced_at = now

    pair = issue_pair(user, device)
    row.replaced_by_id = pair.refresh_row.id
    device.last_seen_at = now
    return user, device, pair


def authenticate_request() -> User | None:
    """The signed-in person for an API request, from its bearer token."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    row = session.scalar(select(AccessToken).where(AccessToken.token_hash == hash_token(header[7:].strip())))
    if row is None or row.revoked_at is not None or row.expires_at <= clock.now():
        return None
    if row.device.unbound_at is not None or not row.user.is_active or row.user.is_locked:
        return None
    g.api_device = row.device
    return row.user
