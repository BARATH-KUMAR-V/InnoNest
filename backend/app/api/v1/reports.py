from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import page_params, staff_only
from app.core.database import get_db
from app.core.security import require_roles
from app.models import Application, AuditEvent, User
from app.schemas.common import AuditOut
from app.services import audit, reports

router = APIRouter(tags=["reports"])


def csv_response(content: str, name: str) -> Response:
    return Response(content, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/reports/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(staff_only)):
    return reports.dashboard(db)


@router.get("/reports/applications.csv")
def applications_csv(status: str | None = None, product: str | None = None, db: Session = Depends(get_db), user: User = Depends(staff_only)):
    query = select(Application).order_by(Application.id)
    if status:
        query = query.where(Application.status.in_(status.split(",")))
    if product:
        query = query.where(Application.product == product)
    return csv_response(reports.register_csv(db, list(db.execute(query).scalars())), "innonest-applications.csv")


@router.get("/reports/decisions.csv")
def decisions_csv(db: Session = Depends(get_db), user: User = Depends(staff_only)):
    return csv_response(reports.decisions_csv(db), "innonest-decisions.csv")


@router.get("/reports/audit.csv")
def audit_csv(db: Session = Depends(get_db), user: User = Depends(require_roles("auditor", "underwriter"))):
    events = list(db.execute(select(AuditEvent).order_by(AuditEvent.id)).scalars())
    return csv_response(reports.audit_csv(events), "innonest-audit.csv")


@router.get("/audit")
def list_audit(application_id: int | None = None, action: str | None = None, actor: str | None = None, page: int = 1, page_size: int = 25,
               db: Session = Depends(get_db), user: User = Depends(staff_only)):
    page, page_size = page_params(page, page_size)
    query = select(AuditEvent)
    if application_id:
        query = query.where(AuditEvent.application_id == application_id)
    if action:
        query = query.where(AuditEvent.action.like(f"{action}%"))
    if actor:
        query = query.where(AuditEvent.actor.like(f"%{actor}%"))
    rows = db.execute(query.order_by(AuditEvent.id.desc())).scalars().all()
    window = rows[(page - 1) * page_size: page * page_size]
    return {"items": [AuditOut.model_validate(r) for r in window], "total": len(rows), "page": page, "page_size": page_size}


@router.get("/audit/verify")
def verify_audit(db: Session = Depends(get_db), user: User = Depends(staff_only)):
    return audit.verify_chain(db)
