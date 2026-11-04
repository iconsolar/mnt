"""People, role templates, per-screen permissions and the audit log."""
from __future__ import annotations

from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base, UtcDateTime


class RoleTemplate(Base):
    __tablename__ = "role_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(64))


class Screen(Base):
    __tablename__ = "screens"

    code: Mapped[str] = mapped_column(String(48), primary_key=True)
    area: Mapped[str] = mapped_column(String(8))  # web or app
    name_key: Mapped[str] = mapped_column(String(80))


class User(UserMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(20))
    role_template_id: Mapped[int] = mapped_column(ForeignKey("role_templates.id"))
    language: Mapped[str] = mapped_column(String(2), default="en")
    status: Mapped[str] = mapped_column(String(8), default="active")  # active, blocked, left
    password_hash: Mapped[str] = mapped_column(String(255))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    # Bumped on password reset and block, so existing web sessions stop working.
    session_epoch: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)

    role: Mapped[RoleTemplate] = relationship(lazy="joined")
    permissions: Mapped[list["UserScreenPermission"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", back_populates="user"
    )

    def get_id(self) -> str:
        return f"{self.id}.{self.session_epoch}"

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def is_locked(self) -> bool:
        return self.locked_at is not None

    def can(self, screen: str, action: str = "view") -> bool:
        for perm in self.permissions:
            if perm.screen_code == screen:
                return perm.can_act if action == "act" else perm.can_view
        return False


class UserScreenPermission(Base):
    __tablename__ = "user_screen_permissions"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    screen_code: Mapped[str] = mapped_column(ForeignKey("screens.code"), primary_key=True)
    can_view: Mapped[bool] = mapped_column(Boolean, default=False)
    can_act: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="permissions")
    screen: Mapped[Screen] = relationship(lazy="joined")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # null: server command
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str] = mapped_column(String(48))
    entity_id: Mapped[str] = mapped_column(String(64))
    before_json: Mapped[dict | None] = mapped_column(JSON)
    after_json: Mapped[dict | None] = mapped_column(JSON)
    at: Mapped[datetime] = mapped_column(UtcDateTime)
