import json
import logging

import worker
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
