import re

from sqlalchemy.orm import Session

from app.models import Application
from app.services import documents as docs
from app.services.catalog import DOC_LABELS, REQUIRED_CONSENTS
from app.services.policies import active_policy
from app.providers.adapters import name_similarity


def first_name(applicant) -> str:
    return applicant.full_name.split()[0].title()


def required_documents(application: Application, policy_params: dict) -> list[dict]:
    items = []
    for applicant in application.applicants:
        items.append({"doc_type": "PAN", "applicant": applicant})
        items.append({"doc_type": "ADDRESS_PROOF", "applicant": applicant})
        if applicant.employment_type in ("SALARIED", "GOVT"):
            items += [{"doc_type": "SALARY_SLIP", "applicant": applicant}, {"doc_type": "BANK_STATEMENT", "applicant": applicant}, {"doc_type": "FORM16", "applicant": applicant}]
        else:
            items += [{"doc_type": "ITR", "applicant": applicant}, {"doc_type": "BANK_STATEMENT", "applicant": applicant}, {"doc_type": "BUSINESS_FINANCIALS", "applicant": applicant}]
            if applicant.annual_turnover:
                items.append({"doc_type": "GST_RETURN", "applicant": applicant})
    items.append({"doc_type": "SALE_AGREEMENT" if application.product == "HOME_LOAN" else "SALE_DEED", "applicant": None})
    items += [{"doc_type": "ENCUMBRANCE_CERTIFICATE", "applicant": None}, {"doc_type": "VALUATION_REPORT", "applicant": None}]
    if application.loan_amount >= policy_params["extra_reports_required_above"][application.product]:
        items += [{"doc_type": "LEGAL_REPORT", "applicant": None}, {"doc_type": "TECHNICAL_REPORT", "applicant": None}]
    return items


def missing_fields(application: Application) -> list[dict]:
    gaps = []
    for applicant in application.applicants:
        who = first_name(applicant)
        checks = [("address", bool(applicant.address.strip()), "current residential address"), ("employer", applicant.employment_type == "SELF_EMPLOYED" or bool(applicant.employer.strip()), "employer name"),
                  ("years_in_job", applicant.years_in_job > 0, "years in current job or business"),
                  ("pan", bool(re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", applicant.pan or "")), "a valid PAN")]
        if applicant.employment_type == "SELF_EMPLOYED":
            checks += [("business_type", bool(applicant.business_type), "business type"), ("annual_turnover", bool(applicant.annual_turnover), "annual turnover"),
                       ("annual_itr_income", bool(applicant.annual_itr_income), "annual income as per your latest ITR")]
        for key, ok, label in checks:
            if not ok:
                gaps.append({"kind": "MISSING_FIELD", "key": f"field:{key}:{applicant.id}", "title": label.capitalize(), "applicant_id": applicant.id, "field": key,
                             "message": f"{who}, please add {label} to the application."})
    property_checks = [("property_address", bool(application.property_address.strip()), "property address"), ("survey_no", bool(application.survey_no.strip()), "survey or plot number"),
                       ("owner_name", bool((application.owner_name or "").strip()), "name of the current property owner"), ("property_pincode", bool(application.property_pincode.strip()), "property pincode"),
                       ("property_area_sqft", application.property_area_sqft > 0, "property area in square feet")]
    if application.product == "HOME_LOAN":
        property_checks.append(("seller_name", bool((application.seller_name or "").strip()), "seller name"))
    else:
        property_checks.append(("end_use", bool(application.end_use), "end use of the loan funds"))
    for key, ok, label in property_checks:
        if not ok:
            gaps.append({"kind": "MISSING_FIELD", "key": f"field:{key}", "title": label.capitalize(), "applicant_id": None, "field": key, "message": f"Please add the {label} to the application."})
    return gaps


def missing_consents(application: Application) -> list[dict]:
    given = application.consents or {}
    return [{"kind": "CONSENT", "key": f"consent:{key}", "title": "Consent: " + text, "applicant_id": None, "field": key,
             "message": f"We need your consent for: {text.lower()}."} for key, text in REQUIRED_CONSENTS.items() if not given.get(key)]


def conflict_items(application: Application, documents: list) -> list[dict]:
    conflicts = []
    for applicant in application.applicants:
        for doc_type in ("PAN", "SALARY_SLIP", "ITR", "BANK_STATEMENT", "ADDRESS_PROOF"):
            fields = docs.field_map(documents, doc_type, applicant.id)
            if not fields:
                continue
            if "name" in fields and name_similarity(fields["name"].effective_value, applicant.full_name) < 85:
                conflicts.append({"key": f"conflict:name:{doc_type}:{applicant.id}", "title": f"Name differs on {DOC_LABELS[doc_type].lower()}", "applicant_id": applicant.id,
                                  "message": f"{first_name(applicant)}, the name on your {DOC_LABELS[doc_type].lower()} ('{fields['name'].effective_value}') does not match the application ('{applicant.full_name}'). Please correct the application or upload the right document, or explain the difference.",
                                  "evidence": {"document": fields["name"].effective_value, "application": applicant.full_name}})
            if "pan" in fields and fields["pan"].effective_value.strip().upper() != applicant.pan.upper():
                conflicts.append({"key": f"conflict:pan:{doc_type}:{applicant.id}", "title": f"PAN differs on {DOC_LABELS[doc_type].lower()}", "applicant_id": applicant.id,
                                  "message": f"The PAN on your {DOC_LABELS[doc_type].lower()} does not match the PAN in the application. Please check and correct one of them.",
                                  "evidence": {"document": fields["pan"].effective_value, "application": applicant.pan}})
        pan_fields = docs.field_map(documents, "PAN", applicant.id)
        if "dob" in pan_fields and pan_fields["dob"].effective_value.strip() != str(applicant.dob):
            conflicts.append({"key": f"conflict:dob:PAN:{applicant.id}", "title": "Date of birth differs on PAN card", "applicant_id": applicant.id,
                              "message": f"{first_name(applicant)}, the date of birth on your PAN card does not match the application. Please check which one is correct.",
                              "evidence": {"document": pan_fields["dob"].effective_value, "application": str(applicant.dob)}})
    for doc_type in ("SALE_AGREEMENT", "SALE_DEED", "ENCUMBRANCE_CERTIFICATE", "VALUATION_REPORT", "LEGAL_REPORT", "TECHNICAL_REPORT"):
        fields = docs.field_map(documents, doc_type)
        if "survey_no" in fields and application.survey_no and fields["survey_no"].effective_value.strip().lower() != application.survey_no.strip().lower():
            conflicts.append({"key": f"conflict:survey:{doc_type}", "title": f"Survey number differs on {DOC_LABELS[doc_type].lower()}", "applicant_id": None,
                              "message": f"The survey number on the {DOC_LABELS[doc_type].lower()} does not match the application. Please confirm the correct number.",
                              "evidence": {"document": fields["survey_no"].effective_value, "application": application.survey_no}})
    deed = docs.field_map(documents, "SALE_DEED")
    if "registered_owner" in deed and application.owner_name and name_similarity(deed["registered_owner"].effective_value, application.owner_name) < 85:
        conflicts.append({"key": "conflict:owner:SALE_DEED", "title": "Property owner differs on title deed", "applicant_id": None,
                          "message": "The registered owner on the title deed does not match the owner named in the application. Please confirm the correct owner.",
                          "evidence": {"document": deed["registered_owner"].effective_value, "application": application.owner_name}})
    return conflicts


def evaluate(db: Session, application: Application) -> dict:
    params = active_policy(db, application.policy_key).params
    documents = docs.active_documents(db, application.id)
    items = []
    for need in required_documents(application, params):
        applicant = need["applicant"]
        applicant_id = applicant.id if applicant else None
        match = next((d for d in reversed(documents) if d.doc_type == need["doc_type"] and (applicant_id is None or d.applicant_id in (None, applicant_id))), None)
        label = DOC_LABELS[need["doc_type"]]
        who = first_name(applicant) + ", please" if applicant else "Please"
        base = {"key": f"doc:{need['doc_type']}:{applicant_id or 0}", "doc_type": need["doc_type"], "title": label, "applicant_id": applicant_id,
                "applicant_name": applicant.full_name if applicant else None, "document_id": match.id if match else None}
        if match is None:
            items.append({**base, "kind": "MISSING_DOCUMENT", "status": "OPEN", "message": f"{who} upload your {label.lower()} as a PDF, PNG or JPG."})
        elif match.extraction_status == "UNREADABLE":
            items.append({**base, "kind": "UNREADABLE_DOCUMENT", "status": "OPEN", "message": f"{who} upload a clearer copy of the {label.lower()}. We could not read the file you sent."})
        elif match.detected_type != need["doc_type"]:
            items.append({**base, "kind": "WRONG_DOCUMENT", "status": "OPEN", "message": f"{who} upload the {label.lower()}. The file you sent reads as a different document."})
        else:
            items.append({**base, "kind": "DOCUMENT", "status": "SATISFIED", "message": f"{label} received"})
    explained = set(application.resolved_conflicts or [])
    for gap in conflict_items(application, documents):
        items.append({**gap, "kind": "CONFLICT", "doc_type": None, "applicant_name": None, "document_id": None, "status": "EXPLAINED" if gap["key"] in explained else "OPEN"})
    for gap in missing_fields(application) + missing_consents(application):
        items.append({**gap, "doc_type": None, "applicant_name": None, "document_id": None, "status": "OPEN"})
    open_items = [i for i in items if i["status"] == "OPEN"]
    return {"complete": not open_items, "open_count": len(open_items), "total": len(items), "items": items}
