import json
import logging

import pytest

import worker
from app.config import Settings
from app.logging_setup import JsonFormatter


def test_worker_tick_runs_without_error():
    worker.run_once()


def test_log_lines_are_json_with_extra_fields():
    record = logging.LogRecord("avirat", logging.INFO, __file__, 1, "signed in", None, None)
    record.employee_code = "E100"
    line = json.loads(JsonFormatter().format(record))
    assert line["message"] == "signed in"
    assert line["level"] == "INFO"
    assert line["employee_code"] == "E100"


def test_a_bad_totp_key_stops_the_app_with_a_clear_message(monkeypatch):
    monkeypatch.setenv("AVIRAT_SECRET_KEY", "s")
    monkeypatch.setenv("AVIRAT_TOTP_KEY", "change-me")
    monkeypatch.setenv("AVIRAT_DATABASE_URL", "mysql+pymysql://x")
    with pytest.raises(RuntimeError, match="Fernet key"):
        Settings.from_env()


def test_change_me_secret_is_refused_in_production(monkeypatch):
    import base64

    monkeypatch.setenv("AVIRAT_ENV", "production")
    monkeypatch.setenv("AVIRAT_SECRET_KEY", "change-me")
    monkeypatch.setenv("AVIRAT_TOTP_KEY", base64.urlsafe_b64encode(b"0" * 32).decode())
    monkeypatch.setenv("AVIRAT_DATABASE_URL", "mysql+pymysql://x")
    with pytest.raises(RuntimeError, match="change-me"):
        Settings.from_env()
