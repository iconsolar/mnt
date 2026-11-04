"""Settings from the environment (.env at the repo root). No secrets in code."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]


def _require(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"{name} is not set. Copy .env.example to .env and fill it in.")
    return value


@dataclass(frozen=True)
class Settings:
    env: str
    secret_key: str
    totp_key: str
    database_url: str
    base_url: str
    port: int
    timezone: str
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(REPO_ROOT / ".env")
        env = os.environ.get("AVIRAT_ENV", "development")
        secret_key = _require("AVIRAT_SECRET_KEY")
        totp_key = _require("AVIRAT_TOTP_KEY")
        if env == "production" and "change-me" in (secret_key, totp_key):
            raise RuntimeError("Replace the change-me secrets in .env before running in production.")
        return cls(
            env=env,
            secret_key=secret_key,
            totp_key=totp_key,
            database_url=_require("AVIRAT_DATABASE_URL"),
            base_url=os.environ.get("AVIRAT_BASE_URL", "https://avirat.iconsolar"),
            port=int(os.environ.get("AVIRAT_PORT", "8080")),
            timezone=os.environ.get("AVIRAT_TIMEZONE", "Asia/Kolkata"),
        )
