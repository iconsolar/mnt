import logging

from flask import jsonify
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..db import session
from . import bp

log = logging.getLogger("avirat.health")


@bp.get("/health")
def health():
    try:
        session.execute(text("select 1"))
    except SQLAlchemyError:
        log.exception("health check: database unreachable")
        return jsonify(status="error", database="unreachable"), 503
    return jsonify(status="ok", database="ok")
