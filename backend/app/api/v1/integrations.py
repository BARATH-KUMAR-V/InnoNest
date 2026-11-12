from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import load_application, operator, staff_only, underwriter_only
from app.core.database import get_db
from app.core.errors import conflict, not_found
from app.core.security import current_user
from app.models import Application, ProviderCall, User, VerificationCheck
from app.providers.adapters import ADAPTERS
from app.providers.base import OUTAGES
from app.providers.service import set_outage
from app.schemas.common import CheckOut, DispositionIn, OutageIn, ProviderCallOut
from app.services import audit, insights, workflow

router = APIRouter(tags=["verification"])

MODE_NOTES = {"MOCK": "Responses are generated locally from deterministic synthetic data.", "SANDBOX": "Responses replay a local sandbox registry shaped like a partner sandbox.",
              "LIVE_PARTNER": "Calls a live partner. No partner credentials are configured in this build."}


@router.get("/integrations")
def list_integrations(user: User = Depends(staff_only)):
    return [{"key": a.key, "name": a.name, "mode": a.mode(), "mode_note": MODE_NOTES[a.mode()], "production_route": a.live_route, "needs_consent": a.needs_consent,
             "simulated_outage": a.key in OUTAGES, "live": False} for a in ADAPTERS.values()]


@router.post("/integrations/{key}/outage")
def toggle_outage(key: str, payload: OutageIn, db: Session = Depends(get_db), user: User = Depends(operator)):
    if key not in ADAPTERS:
        raise not_found("Provider")
    set_outage(key, payload.down)
    audit.record(db, "integration.outage_toggled", actor=user.email, actor_role=user.role, details={"provider": key, "down": payload.down})
    db.commit()
    return {"key": key, "simulated_outage": key in OUTAGES}


@router.get("/applications/{application_id}/provider-calls", response_model=list[ProviderCallOut])
def provider_calls(application: Application = Depends(load_application), db: Session = Depends(get_db), user: User = Depends(staff_only)):
    return list(db.execute(select(ProviderCall).where(ProviderCall.application_id == application.id).order_by(ProviderCall.id)).scalars())


@router.get("/applications/{application_id}/verification", response_model=list[CheckOut])
def verification(application: Application = Depends(load_application), db: Session = Depends(get_db), user: User = Depends(staff_only)):
    return insights.latest_checks(db, application.id)


@router.post("/applications/{application_id}/verification/{check_id}/disposition", response_model=CheckOut)
def disposition(check_id: int, payload: DispositionIn, application: Application = Depends(load_application), db: Session = Depends(get_db), user: User = Depends(underwriter_only)):
    check = db.get(VerificationCheck, check_id)
    if not check or check.application_id != application.id:
        raise not_found("Verification check")
    if check.status not in ("FLAG", "REFER"):
        raise conflict("Only a flagged or referred check needs a disposition")
    if application.status != "REFERRED":
        raise conflict("Checks can only be dispositioned while the application is referred")
    check.disposition, check.disposition_note, check.disposition_by = payload.disposition, payload.note, user.id
    audit.record(db, "verification.disposition", application.id, user.email, user.role, "verification_check", check.id, {"code": check.code, "disposition": payload.disposition, "note": payload.note})
    db.commit()
    return check


@router.post("/applications/{application_id}/retry-verification")
def retry_verification(application: Application = Depends(load_application), db: Session = Depends(get_db), user: User = Depends(operator)):
    workflow.retry_verification(db, application, user)
    db.commit()
    return {"status": application.status}


@router.post("/applications/{application_id}/reevaluate")
def reevaluate(application: Application = Depends(load_application), db: Session = Depends(get_db), user: User = Depends(underwriter_only)):
    if application.status != "REFERRED":
        raise conflict("Only a referred application can be re-evaluated")
    audit.record(db, "application.reevaluated", application.id, user.email, user.role, "application", application.id)
    workflow.run_pipeline(db, application, "reviewer re-evaluation")
    db.commit()
    return {"status": application.status}
