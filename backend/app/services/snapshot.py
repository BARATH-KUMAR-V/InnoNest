from datetime import date

from sqlalchemy.orm import Session

from app.models import Application, VerificationCheck
from app.providers.service import latest_calls
from app.services import documents as docs, income, property_assessment
from app.services.finance import age_on
from app.services.verification import call_for


def bureau_summary(applicants: list, calls: list) -> dict:
    scores, dpd, enquiries, utilization = [], [], [], []
    for applicant in applicants:
        call = call_for(calls, "bureau", applicant.id)
        if call and call.response_status == "OK":
            scores.append(call.response["score"])
            dpd.append(call.response["max_dpd_12m"])
            enquiries.append(call.response["enquiries_6m"])
            utilization.append(call.response["utilization"])
    if not scores:
        return {"score": None, "max_dpd_12m": 0, "enquiries_6m": 0, "utilization": 0.0, "available": False}
    return {"score": min(scores), "max_dpd_12m": max(dpd), "enquiries_6m": max(enquiries), "utilization": max(utilization), "available": True}


def check_rows(rows: list[VerificationCheck]) -> list[dict]:
    result = []
    for row in rows:
        status = "PASS" if row.disposition == "CLEARED" else row.status
        result.append({"category": row.category, "code": row.code, "status": status, "applicant_id": row.applicant_id})
    return result


def build(db: Session, application: Application, params: dict, checks: list[VerificationCheck], today: date | None = None) -> dict:
    today = today or date.today()
    calls = latest_calls(db, application.id)
    documents = docs.active_documents(db, application.id)
    applicants = []
    for applicant in application.applicants:
        assessed = income.assess(applicant, calls, documents, params)
        assessed["age_years"] = round(age_on(applicant.dob, today), 2)
        assessed["years_in_job"] = applicant.years_in_job
        applicants.append(assessed)
    prop = property_assessment.assess(application, calls, documents, params)
    gst = call_for(calls, "gst", application.applicants[0].id)
    required = [c for c in checks]
    return {
        "product": application.product, "loan_amount": application.loan_amount, "interest_rate": application.interest_rate, "tenure_months": application.tenure_months,
        "end_use": application.end_use, "property_type": application.property_type, "applicants": applicants, "bureau": bureau_summary(list(application.applicants), calls),
        "checks": check_rows(required), "property": prop, "gst_regular": bool(gst and gst.response_status == "OK" and gst.response.get("filing_regular")),
        "explained_conflicts": list(application.resolved_conflicts or []), "as_of": today.isoformat(),
    }
