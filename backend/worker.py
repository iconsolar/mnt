"""Worker process: wakes every 30 s. Timers and notification sending come in stage 3."""
from __future__ import annotations

import logging
import threading

from app.logging_setup import configure_logging

INTERVAL_SECONDS = 30
log = logging.getLogger("avirat.worker")


def run_once() -> None:
    log.info("worker tick")


def main(stop: threading.Event | None = None) -> None:
    configure_logging()
    stop = stop or threading.Event()
    log.info("worker started")
    while not stop.is_set():
        run_once()
        stop.wait(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
