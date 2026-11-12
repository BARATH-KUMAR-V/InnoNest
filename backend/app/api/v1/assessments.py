from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import load_application, policy_admin_only, staff_only, underwriter_only
from app.core.database import get_db
from app.core.errors import not_found
from app.core.security import current_user
from app.models import Application, Assessment, Decision, User
from app.schemas.common import DecisionOut, EligibilityIn, EmiIn, PolicyOut, PolicyUpdate, ReviewIn
from app.services import finance, insights, policies, workflow
from app.services.engine import financials

router = APIRouter(tags=["assessment"])


def latest_assessment(db: Session, application_id: int) -> Assessment:
    row = db.execute(select(Assessment).where(Assessment.application_id == application_id).order_by(Assessment.id.desc()).limit(1)).scalar_one_or_none()
    if not row:
        raise not_found("Assessment for this application. Underwriting has not run yet")
    return row


@router.post("/calculations/emi")
def calculate_emi(payload: EmiIn, user: User = Depends(current_user)):
    emi = finance.emi(payload.principal, payload.annual_rate, payload.months)
    schedule = finance.amortization(payload.principal, payload.annual_rate, payload.months)
    return {"emi": round(emi, 2), "total_payable": round(emi * payload.months, 2), "total_interest": round(emi * payload.months - payload.principal, 2),
            "formula": "P x r x (1+r)^n / ((1+r)^n - 1), r = annual rate / 12 / 100", "schedule_preview": schedule[:12]}


@router.post("/calculations/eligibility")
def calculate_eligibility(payload: EligibilityIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    policy = policies.active_policy(db, payload.policy_key)
    params = policy.params
    income = payload.monthly_income + payload.other_income * params["other_income_recognition"]
    limit = params["foir_limit"][payload.employment_type]
    ltv_cap = financials.ltv_limit_for(params["ltv_limit"][payload.product], payload.loan_amount or payload.property_value)
    max_emi = finance.max_eligible_emi(income, payload.existing_emi, limit)
    by_foir = finance.max_principal(max_emi, payload.interest_rate, payload.tenure_months)
    by_ltv = payload.property_value * ltv_cap
    result = {"policy": f"{policy.name} v{policy.version}", "eligible_income": round(income, 2), "foir_limit": limit, "ltv_limit": ltv_cap, "max_eligible_emi": round(max_emi, 2),
              "loan_by_foir": round(by_foir, 2), "loan_by_ltv": round(by_ltv, 2), "indicative_eligible_loan": round(min(by_foir, by_ltv), 2)}
    if payload.loan_amount:
        emi = finance.emi(payload.loan_amount, payload.interest_rate, payload.tenure_months)
        result.update(proposed_emi=round(emi, 2), foir=round(finance.foir(payload.existing_emi, emi, income), 4), ltv=round(finance.ltv(payload.loan_amount, payload.property_value), 4))
    return result


@router.get("/applications/{application_id}/financial")
def financial(application: Application = Depends(load_application), db: Session = Depends(get_db), user: User = Depends(staff_only)):
    row = latest_assessment(db, application.id)
    decision = insights.latest_decision(db, application.id)
    return {"financial": row.financial, "income": decision.inputs["applicants"] if decision else [], "run": row.run}


@router.get("/applications/{application_id}/risk")
def risk(application: Application = Depends(load_application), db: Session = Depends(get_db), user: User = Depends(staff_only)):
    return latest_assessment(db, application.id).risk


@router.get("/applications/{application_id}/property")
def property_view(application: Application = Depends(load_application), db: Session = Depends(get_db), user: User = Depends(staff_only)):
    return latest_assessment(db, application.id).property_assessment


@router.get("/policies", response_model=list[PolicyOut])
def list_policies(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return policies.list_active(db)


@router.get("/policies/{key}/history", response_model=list[PolicyOut])
def policy_history(key: str, db: Session = Depends(get_db), user: User = Depends(staff_only)):
    rows = policies.history(db, key)
    if not rows:
        raise not_found("Policy")
    return rows


@router.put("/policies/{key}", response_model=PolicyOut)
def update_policy(key: str, payload: PolicyUpdate, db: Session = Depends(get_db), user: User = Depends(policy_admin_only)):
    policy = policies.publish_version(db, key, payload.params, payload.change_note, user.email, user.role)
    db.commit()
    return policy


@router.get("/applications/{application_id}/compare-policies")
def compare(application: Application = Depends(load_application), db: Session = Depends(get_db), user: User = Depends(staff_only)):
    return insights.compare_policies(db, application)


@router.get("/applications/{application_id}/decisions", response_model=list[DecisionOut])
def decisions(application: Application = Depends(load_application), db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = list(db.execute(select(Decision).where(Decision.application_id == application.id).order_by(Decision.id.desc())).scalars())
    if user.role == "applicant":
        return [DecisionOut.model_validate(r).model_copy(update={"inputs": {}, "outputs": {}, "evidence_refs": []}) for r in rows]
    return rows


@router.get("/decisions/{decision_id}/replay")
def replay(decision_id: int, db: Session = Depends(get_db), user: User = Depends(staff_only)):
    decision = db.get(Decision, decision_id)
    if not decision:
        raise not_found("Decision")
    return insights.replay(decision)


@router.post("/applications/{application_id}/review", response_model=DecisionOut)
def review(payload: ReviewIn, application: Application = Depends(load_application), db: Session = Depends(get_db), user: User = Depends(underwriter_only)):
    decision = workflow.manual_review(db, application, user, payload.outcome, payload.note)
    db.commit()
    return decision


@router.get("/applications/{application_id}/evidence-graph")
def evidence_graph(include_fields: bool = True, application: Application = Depends(load_application), db: Session = Depends(get_db), user: User = Depends(staff_only)):
    return insights.evidence_graph(db, application, include_fields)
