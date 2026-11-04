"""Device binding, tokens, login attempts and TOTP."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Computed, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base, UtcDateTime
from ..people.models import User


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    install_id: Mapped[str] = mapped_column(String(64), index=True)
    model: Mapped[str | None] = mapped_column(String(80))
    os_version: Mapped[str | None] = mapped_column(String(32))
    app_version: Mapped[str | None] = mapped_column(String(32))
    fcm_token: Mapped[str | None] = mapped_column(String(255))
    bound_at: Mapped[datetime] = mapped_column(UtcDateTime)
    unbound_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    unbound_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    last_seen_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    # The database itself allows one bound phone per person and one person per bound
    # phone (D-12). Unbound rows stay as history, with these columns null.
    active_user_id: Mapped[int | None] = mapped_column(
        BigInteger, Computed("if(`unbound_at` is null, `user_id`, null)", persisted=True), unique=True
    )
    active_install_id: Mapped[str | None] = mapped_column(
        String(64), Computed("if(`unbound_at` is null, `install_id`, null)", persisted=True), unique=True
    )

    user: Mapped[User] = relationship(foreign_keys=[user_id])


class AccessToken(Base):
    __tablename__ = "access_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    issued_at: Mapped[datetime] = mapped_column(UtcDateTime)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    user: Mapped[User] = relationship()
    device: Mapped[Device] = relationship()


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    issued_at: Mapped[datetime] = mapped_column(UtcDateTime)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime)
    replaced_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    replaced_by_id: Mapped[int | None] = mapped_column(ForeignKey("refresh_tokens.id"))
    grace_used_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    user: Mapped[User] = relationship()
    device: Mapped[Device] = relationship()


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_code: Mapped[str] = mapped_column(String(32), index=True)
    device_install_id: Mapped[str | None] = mapped_column(String(64))
    ip: Mapped[str | None] = mapped_column(String(45))
    at: Mapped[datetime] = mapped_column(UtcDateTime)
    success: Mapped[bool] = mapped_column()
    reason: Mapped[str | None] = mapped_column(String(32))


class TotpSecret(Base):
    __tablename__ = "totp_secrets"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    secret_encrypted: Mapped[str] = mapped_column(String(255))
    enrolled_at: Mapped[datetime] = mapped_column(UtcDateTime)
    # The last 30-second step accepted, so a code can't be used twice.
    last_used_step: Mapped[int | None] = mapped_column(BigInteger)


class TotpRecoveryCode(Base):
    __tablename__ = "totp_recovery_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    used_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
