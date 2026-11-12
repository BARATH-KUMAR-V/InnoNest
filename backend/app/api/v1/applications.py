from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import load_application, page_params
from app.core.database import get_db
from app.core.errors import conflict, forbidden, invalid
from app.core.security import current_user
from app.models import Applicant, Application, AuditEvent, DocumentRequest, User
from app.schemas.common import ApplicationCreate, ApplicationOut, ApplicationRow, ApplicationUpdate, ClarificationIn, ConsentIn, RequestOut
from app.services import audit, checklist, workflow
from app.services.catalog import EDITABLE_STATUSES, REQUIRED_CONSENTS

router = APIRouter(prefix="/applications", tags=["applications"])

SORTABLE = {"created_at": Application.created_at, "loan_amount": Application.loan_amount, "status": Application.status, "reference": Application.reference, "decided_at": Application.decided_at}
TIMELINE_ACTIONS = ("application.submitted", "application.status_changed", "document.uploaded", "followup.request_created", "followup.request_fulfilled", "followup.reminder_sent",
                    "notification.created", "application.clarification", "application.updated", "decision.recorded", "decision.reviewed", "application.expired", "application.consent")


def new_reference(db: Session) -> str:
    latest = db.execute(select(func.max(Application.id))).scalar() or 0
    return f"INN-{date.today().year}-{latest + 1:06d}"


def apply_applicant(applicant: Applicant, data: dict) -> None:
    for key, value in data.items():
        if key != "id":
            setattr(applicant, key, value)


@router.post("", response_model=ApplicationOut, status_code=201)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role != "applicant":
        raise forbidden("Only applicants can start an application")
    fields = payload.model_dump(exclude={"applicants"})
    application = Application(reference=new_reference(db), owner_id=user.id, status="DRAFT", **fields)
    for item in payload.applicants:
        data = item.model_dump(exclude={"id"})
        application.applicants.append(Applicant(**data))
    db.add(application)
    db.flush()
    audit.record(db, "application.created", application.id, user.email, user.role, "application", application.id, {"product": application.product, "loan_amount": application.loan_amount})
    db.commit()
    return application


@router.get("")
def list_applications(q: str | None = None, status: str | None = None, product: str | None = None, sort: str = "created_at", order: str = "desc",
                      page: int = 1, page_size: int = 20, db: Session = Depends(get_db), user: User = Depends(current_user)):
    page, page_size = page_params(page, page_size)
    primary = select(Applicant.application_id, Applicant.full_name, Applicant.employment_type).where(Applicant.role == "PRIMARY").subquery()
    query = select(Application, primary.c.full_name, primary.c.employment_type).join(primary, primary.c.application_id == Application.id, isouter=True)
    if user.role == "applicant":
        query = query.where(Application.owner_id == user.id)
    if q:
        like = f"%{q.strip().lower()}%"
        query = query.where(or_(func.lower(Application.reference).like(like), func.lower(primary.c.full_name).like(like), func.lower(Application.property_city).like(like)))
    if status:
        query = query.where(Application.status.in_(status.split(",")))
    if product:
        query = query.where(Application.product == product)
    column = SORTABLE.get(sort, Application.created_at)
    query = query.order_by(column.asc() if order == "asc" else column.desc(), Application.id.desc())
    total = db.execute(select(func.count()).select_from(query.order_by(None).subquery())).scalar()
    rows = db.execute(query.limit(page_size).offset((page - 1) * page_size)).all()
    items = [ApplicationRow.model_validate({**{c: getattr(a, c) for c in ApplicationRow.model_fields if hasattr(a, c)}, "applicant_name": name, "employment_type": emp}) for a, name, emp in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{application_id}", response_model=ApplicationOut)
def get_application(application: Application = Depends(load_application)):
    return application


@router.patch("/{application_id}", response_model=ApplicationOut)
def update_application(payload: ApplicationUpdate, application: Application = Depends(load_application), db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role != "applicant":
        raise forbidden("Only the applicant can edit the application")
    workflow.ensure_editable(application)
    changes = payload.model_dump(exclude_unset=True, exclude={"applicants"})
    for key, value in changes.items():
        setattr(application, key, value)
    if payload.applicants is not None:
        existing = {a.id: a for a in application.applicants}
        for item in payload.applicants:
            if item.id not in existing:
                raise invalid("Applicants can only be updated by their id", [{"field": "applicants", "message": f"Unknown applicant id {item.id}"}])
            data = item.model_dump(exclude={"id", "role"})
            apply_applicant(existing[item.id], data)
            changes[f"applicant_{item.id}"] = sorted(data)
    audit.record(db, "application.updated", application.id, user.email, user.role, "application", application.id, {"fields": sorted(changes)})
    db.flush()
    workflow.revalidate(db, application, user, "applicant updated the application")
    db.commit()
    return application


@router.post("/{application_id}/consents", response_model=ApplicationOut)
def give_consents(payload: ConsentIn, application: Application = Depends(load_application), db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role != "applicant":
        raise forbidden("Only the applicant can give consent")
    workflow.ensure_editable(application)
    unknown = [k for k in payload.scopes if k not in REQUIRED_CONSENTS]
    if unknown:
        raise invalid("Unknown consent scope", [{"field": "scopes", "message": ", ".join(unknown)}])
    application.consents = {**(application.consents or {}), **payload.scopes}
    audit.record(db, "application.consent", application.id, user.email, user.role, "application", application.id, {"scopes": payload.scopes})
    db.flush()
    workflow.revalidate(db, application, user, "applicant gave consent")
    db.commit()
    return application


@router.post("/{application_id}/submit", response_model=ApplicationOut)
def submit_application(application: Application = Depends(load_application), db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role != "applicant":
        raise forbidden("Only the applicant can submit the application")
    workflow.submit(db, application, user)
    db.commit()
    return application


@router.post("/{application_id}/withdraw", response_model=ApplicationOut)
def withdraw_application(application: Application = Depends(load_application), db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role != "applicant":
        raise forbidden("Only the applicant can withdraw the application")
    workflow.withdraw(db, application, user)
    db.commit()
    return application


@router.get("/{application_id}/checklist")
def get_checklist(application: Application = Depends(load_application), db: Session = Depends(get_db)):
    return checklist.evaluate(db, application)


@router.get("/{application_id}/requests", response_model=list[RequestOut])
def get_requests(application: Application = Depends(load_application)):
    return application.requests


@router.post("/{application_id}/clarifications", response_model=RequestOut)
def submit_clarification(payload: ClarificationIn, application: Application = Depends(load_application), db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role != "applicant":
        raise forbidden("Only the applicant can respond to a request")
    request = db.get(DocumentRequest, payload.request_id)
    if not request or request.application_id != application.id:
        raise invalid("That request does not belong to this application")
    if request.status != "OPEN":
        raise conflict("That request is no longer open")
    if request.kind != "CONFLICT":
        raise invalid("Only an information conflict can be answered with an explanation. Upload the document or update the application instead")
    request.response = payload.response.strip()
    conflict_key = request.item_key
    application.resolved_conflicts = sorted(set(application.resolved_conflicts or []) | {conflict_key})
    audit.record(db, "application.clarification", application.id, user.email, user.role, "document_request", request.id, {"item_key": conflict_key, "response": request.response})
    db.flush()
    workflow.revalidate(db, application, user, "applicant submitted a clarification")
    db.commit()
    return request


@router.get("/{application_id}/history")
def get_history(application: Application = Depends(load_application), db: Session = Depends(get_db)):
    events = db.execute(select(AuditEvent).where(AuditEvent.application_id == application.id, AuditEvent.action.in_(TIMELINE_ACTIONS)).order_by(AuditEvent.id)).scalars().all()
    return [{"id": e.id, "action": e.action, "actor": e.actor, "at": e.created_at.isoformat(), "details": e.details} for e in events]
