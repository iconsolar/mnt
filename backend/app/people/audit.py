"""Audit log for every admin change, written in the caller's transaction."""
from __future__ import annotations

from .. import clock
from ..db import session
from .models import AuditLog


def record(action: str, entity: str, entity_id, *, actor=None, before: dict | None = None, after: dict | None = None) -> None:
    """Add an audit row. The caller commits, so the row and the change land together."""
    session.add(
        AuditLog(
            actor_user_id=actor.id if actor is not None else None,
            action=action,
            entity=entity,
            entity_id=str(entity_id),
            before_json=before,
            after_json=after,
            at=clock.now(),
        )
    )
