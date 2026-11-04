"""JSON API for the phone app, under /api/v1."""
from flask import Blueprint

bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")

from ..auth import api as _auth_api  # noqa: E402,F401
from . import health  # noqa: E402,F401
