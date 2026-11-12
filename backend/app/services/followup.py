from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import branding
from app.core.config import settings
from app.models import Application, DocumentRequest, Notification, Setting
from app.models.mixins import utcnow
from app.services import audit, messaging


def follow_up_config(db: Session) -> dict:
    row = db.get(Setting, "follow_up")
    stored = row.value if row else {}
    return {"reminder_intervals_hours": stored.get("reminder_intervals_hours", settings.reminder_intervals_hours), "expiry_days": stored.get("expiry_days", settings.expiry_days)}


def save_follow_up_config(db: Session, intervals: list[int], expiry_days: int, actor: str, role: str) -> dict:
    row = db.get(Setting, "follow_up") or Setting(key="follow_up", value={})
    row.value = {"reminder_intervals_hours": intervals, "expiry_days": expiry_days}
    db.add(row)
    db.flush()
    audit.record(db, "followup.config_changed", actor=actor, actor_role=role, entity="setting", details=row.value)
    return row.value


def signed(body: str) -> str:
    return f"{body}\n\n{branding.NAME}\n{branding.TAGLINE}"


def notify(db: Session, application: Application, kind: str, subject: str, body: str) -> list[Notification]:
    primary = application.applicants[0]
    channels = [("IN_APP", None, "DELIVERED", False)]
    email = messaging.email_channel()
    sms = messaging.sms_channel()
    channels.append(("EMAIL", primary.email, email.send(primary.email, f"{branding.NAME}: {subject}", signed(body)), email.simulated))
    channels.append(("SMS", primary.phone, sms.send(primary.phone, f"{branding.NAME}: {subject}", signed(body)), sms.simulated))
    rows = []
    for channel, recipient, status, simulated in channels:
        row = Notification(application_id=application.id, user_id=application.owner_id, channel=channel, kind=kind, subject=f"{branding.NAME}: {subject}", body=signed(body),
                           delivery_status=status, simulated=simulated if channel != "IN_APP" else False, recipient=recipient, created_at=utcnow())
        db.add(row)
        rows.append(row)
    db.flush()
    audit.record(db, "notification.created", application.id, details={"kind": kind, "channels": [r.channel for r in rows], "subject": subject})
    return rows


def request_message(items: list[dict]) -> str:
    lines = [item["message"] if isinstance(item, dict) else item.message for item in items]
    return "\n".join(f"- {line}" for line in lines)


def sync_requests(db: Session, application: Application, items: list[dict], due: datetime | None = None) -> dict:
    existing = {r.item_key: r for r in application.requests if r.status in ("OPEN", "RESPONDED")}
    created, fulfilled = [], []
    open_keys = {i["key"] for i in items if i["status"] == "OPEN"}
    explained_keys = {i["key"] for i in items if i["status"] == "EXPLAINED"}
    for item in items:
        if item["status"] != "OPEN" or item["key"] in existing:
            continue
        request = DocumentRequest(application_id=application.id, applicant_id=item.get("applicant_id"), kind=item["kind"], item_key=item["key"], title=item["title"],
                                  message=item["message"], status="OPEN", due_at=due)
        application.requests.append(request)
        created.append(request)
    db.flush()
    for key, request in existing.items():
        if key in open_keys:
            continue
        request.status = "RESPONDED" if key in explained_keys else "FULFILLED"
        request.fulfilled_at = utcnow()
        fulfilled.append(request)
    for request in created:
        audit.record(db, "followup.request_created", application.id, entity="document_request", entity_id=request.id, details={"kind": request.kind, "item_key": request.item_key, "title": request.title})
    for request in fulfilled:
        audit.record(db, "followup.request_fulfilled", application.id, entity="document_request", entity_id=request.id, details={"item_key": request.item_key, "status": request.status})
    return {"created": created, "fulfilled": fulfilled}


def open_requests(application: Application) -> list[DocumentRequest]:
    return [r for r in application.requests if r.status == "OPEN"]


def send_due_reminders(db: Session, now: datetime | None = None) -> list[dict]:
    now = now or utcnow()
    config = follow_up_config(db)
    intervals = config["reminder_intervals_hours"]
    sent = []
    apps = db.execute(select(Application).where(Application.status == "ACTION_REQUIRED")).scalars().all()
    for application in apps:
        if application.expires_at and now >= application.expires_at:
            application.status = "EXPIRED"
            application.pending_stage = None
            for request in open_requests(application):
                request.status = "EXPIRED"
            notify(db, application, "EXPIRED", f"Application {application.reference} has expired",
                   "We did not receive the requested information in time, so the application has expired. You can start a new application at any time.")
            audit.record(db, "application.expired", application.id, details={"expires_at": application.expires_at.isoformat()})
            sent.append({"application": application.reference, "action": "EXPIRED"})
            continue
        pending = open_requests(application)
        if not pending:
            continue
        index = min(r.reminders_sent for r in pending)
        if index >= len(intervals):
            continue
        base = max((r.last_reminded_at or r.created_at) for r in pending)
        if now < base + timedelta(hours=intervals[index]):
            continue
        who = application.applicants[0].full_name.split()[0].title()
        body = f"{who}, we are still waiting for the following items on application {application.reference}:\n{request_message([{'message': r.message} for r in pending])}"
        notify(db, application, "REMINDER", f"Reminder: action needed on application {application.reference}", body)
        for request in pending:
            request.reminders_sent += 1
            request.last_reminded_at = now
        audit.record(db, "followup.reminder_sent", application.id, details={"reminder_number": index + 1, "open_items": [r.item_key for r in pending]})
        sent.append({"application": application.reference, "action": "REMINDER", "number": index + 1})
    db.flush()
    return sent
