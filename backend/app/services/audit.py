import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent
from app.models.mixins import utcnow


def _digest(prev_hash: str, payload: dict) -> str:
    raw = prev_hash + json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def record(db: Session, action: str, application_id: int | None = None, actor: str = "system", actor_role: str = "system",
           entity: str | None = None, entity_id: int | None = None, details: dict | None = None) -> AuditEvent:
    last = db.execute(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1)).scalar_one_or_none()
    prev_hash = last.hash if last else "0" * 64
    created = utcnow()
    details = details or {}
    payload = {"application_id": application_id, "actor": actor, "action": action, "entity": entity, "entity_id": entity_id,
               "details": details, "at": created.isoformat()}
    event = AuditEvent(application_id=application_id, actor=actor, actor_role=actor_role, action=action, entity=entity,
                       entity_id=entity_id, details=details, prev_hash=prev_hash, hash=_digest(prev_hash, payload), created_at=created)
    db.add(event)
    db.flush()
    return event


def verify_chain(db: Session) -> dict:
    prev_hash = "0" * 64
    count = 0
    for event in db.execute(select(AuditEvent).order_by(AuditEvent.id)).scalars():
        payload = {"application_id": event.application_id, "actor": event.actor, "action": event.action, "entity": event.entity,
                   "entity_id": event.entity_id, "details": event.details, "at": event.created_at.isoformat()}
        if event.prev_hash != prev_hash or event.hash != _digest(prev_hash, payload):
            return {"intact": False, "broken_at": event.id, "checked": count}
        prev_hash = event.hash
        count += 1
    return {"intact": True, "broken_at": None, "checked": count}
