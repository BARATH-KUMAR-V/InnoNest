from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import operator, page_params
from app.core.database import get_db
from app.core.errors import not_found
from app.core.security import current_user
from app.models import Notification, User
from app.models.mixins import utcnow
from app.schemas.common import FollowUpConfig, FollowUpRun, NotificationOut
from app.services import audit, followup

router = APIRouter(tags=["follow-up"])


@router.get("/notifications")
def list_notifications(application_id: int | None = None, channel: str | None = None, unread: bool = False, page: int = 1, page_size: int = 20,
                       db: Session = Depends(get_db), user: User = Depends(current_user)):
    page, page_size = page_params(page, page_size)
    query = select(Notification).where(Notification.user_id == user.id)
    if user.role != "applicant":
        query = select(Notification)
    if application_id:
        query = query.where(Notification.application_id == application_id)
    if channel:
        query = query.where(Notification.channel == channel.upper())
    if unread:
        query = query.where(Notification.read_at.is_(None))
    rows = db.execute(query.order_by(Notification.id.desc())).scalars().all()
    unread_count = sum(1 for r in rows if r.read_at is None and r.channel == "IN_APP")
    window = rows[(page - 1) * page_size: page * page_size]
    return {"items": [NotificationOut.model_validate(r) for r in window], "total": len(rows), "page": page, "page_size": page_size, "unread_in_app": unread_count}


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.get(Notification, notification_id)
    if not row or (user.role == "applicant" and row.user_id != user.id):
        raise not_found("Notification")
    row.read_at = row.read_at or utcnow()
    db.commit()
    return row


@router.post("/notifications/read-all")
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.execute(select(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))).scalars().all()
    for row in rows:
        row.read_at = utcnow()
    db.commit()
    return {"marked": len(rows)}


@router.get("/follow-up/config")
def get_config(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return followup.follow_up_config(db)


@router.put("/follow-up/config")
def put_config(payload: FollowUpConfig, db: Session = Depends(get_db), user: User = Depends(operator)):
    saved = followup.save_follow_up_config(db, payload.reminder_intervals_hours, payload.expiry_days, user.email, user.role)
    db.commit()
    return saved


@router.post("/follow-up/run")
def run_sweep(payload: FollowUpRun, db: Session = Depends(get_db), user: User = Depends(operator)):
    now = utcnow() + timedelta(hours=payload.advance_hours)
    actions = followup.send_due_reminders(db, now)
    audit.record(db, "followup.sweep_run", actor=user.email, actor_role=user.role, details={"advance_hours": payload.advance_hours, "actions": actions})
    db.commit()
    return {"as_of": now.isoformat(), "actions": actions}
