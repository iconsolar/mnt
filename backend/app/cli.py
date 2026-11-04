"""Server commands: seed, first Super Admin, and the unlocks that have no screen."""
from __future__ import annotations

import click
from flask import Flask
from flask.cli import AppGroup
from sqlalchemy import select

from .auth import totp
from .auth.login import hash_password, unlock
from .db import session
from .people import audit, service
from .people.models import User


def _find(employee_code: str) -> User:
    user = session.scalar(select(User).where(User.employee_code == employee_code))
    if user is None:
        raise click.ClickException(f"No person with employee code {employee_code}")
    return user


def register_cli(app: Flask) -> None:
    @app.cli.command("seed")
    def seed():
        """Create or update screens and role templates from code."""
        service.seed_registry()
        session.commit()
        click.echo("Seeded screens and role templates.")

    users = AppGroup("users", help="Accounts that need the server, not a screen.")

    @users.command("create-superadmin")
    @click.argument("employee_code")
    @click.option("--name", default=None, help="Full name; defaults to the employee code.")
    def create_superadmin(employee_code, name):
        """Create a Super Admin and print a one-time password once."""
        service.seed_registry()
        session.flush()
        if session.scalar(select(User).where(User.employee_code == employee_code)) is not None:
            raise click.ClickException(f"{employee_code} already exists")
        password = service.generate_one_time_password()
        service.create_person(
            employee_code=employee_code,
            name=name or employee_code,
            phone=None,
            role=service.role_by_code("super_admin"),
            language="en",
            password_hash=hash_password(password),
            actor=None,
        )
        session.commit()
        click.echo(f"One-time password for {employee_code}: {password}")
        click.echo("It is not stored anywhere. It must be changed at first sign-in.")

    @users.command("unlock")
    @click.argument("employee_code")
    def unlock_user(employee_code):
        """Unlock an account. The only way to unlock a Super Admin (D-54)."""
        user = _find(employee_code)
        unlock(user)
        audit.record("person.unlock", "user", user.id, after={"via": "server command"})
        session.commit()
        click.echo(f"Unlocked {employee_code}.")

    @users.command("reset-totp")
    @click.argument("employee_code")
    def reset_totp(employee_code):
        """Remove TOTP and recovery codes; the person enrols again at next sign-in."""
        user = _find(employee_code)
        totp.reset(user)
        audit.record("totp.reset", "user", user.id, after={"via": "server command"})
        session.commit()
        click.echo(f"TOTP reset for {employee_code}.")

    app.cli.add_command(users)
