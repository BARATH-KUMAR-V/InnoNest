from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Applicant, Application, Document, ProviderCall, VerificationCheck
from app.providers.adapters import name_similarity
from app.providers.service import APPLICANT_PROVIDERS, latest_calls
from app.services import checklist, documents as docs
from app.services.catalog import OPEN_STATUSES

SEVERITY_WEIGHT = {"HIGH": 0.30, "MEDIUM": 0.10}
INDICATOR_WEIGHTS = {"income_vs_bank": 0.25, "form16_vs_slip": 0.15, "returned_cheques": 0.10, "undisclosed_obligation": 0.20}


def check(category: str, code: str, title: str, status: str, detail: str, applicant_id: int | None = None, evidence: dict | None = None) -> dict:
    return {"category": category, "code": code, "title": title, "status": status, "detail": detail, "applicant_id": applicant_id, "evidence": evidence or {}}


def call_for(calls: list[ProviderCall], provider: str, applicant_id: int | None) -> ProviderCall | None:
    return next((c for c in calls if c.provider == provider and (provider not in APPLICANT_PROVIDERS or c.applicant_id == applicant_id)), None)


def not_checked(category: str, code: str, title: str, call: ProviderCall | None, applicant_id: int | None) -> dict:
    reason = "no response was recorded" if call is None else f"provider response was {call.response_status.lower().replace('_', ' ')}"
    return check(category, code, title, "NOT_CHECKED", f"The check was not performed because {reason}.", applicant_id)


def kyc_checks(application: Application, applicant: Applicant, calls: list[ProviderCall], documents: list[Document]) -> list[dict]:
    out = []
    pan = call_for(calls, "pan", applicant.id)
    if pan is None or pan.response_status != "OK":
        out.append(not_checked("KYC", "KYC-PAN", "PAN verification", pan, applicant.id))
    else:
        mapping = {"VERIFIED": "PASS", "PARTIAL": "FLAG", "MISMATCH": "REFER", "NOT_FOUND": "FAIL"}
        status = mapping[pan.verification_result]
        detail = {"PASS": "PAN registry name and date of birth match the application.", "FLAG": "PAN registry name differs slightly from the application name.",
                  "REFER": "PAN registry name or date of birth does not match the application.", "FAIL": "The PAN is not in a valid format."}[status]
        out.append(check("KYC", "KYC-PAN", "PAN verification", status, detail, applicant.id,
                         {"registry_name": pan.response.get("registry_name"), "application_name": applicant.full_name, "source_ref": pan.source_ref, "mode": pan.mode}))
    aadhaar = call_for(calls, "aadhaar", applicant.id)
    if aadhaar is None or aadhaar.response_status != "OK":
        out.append(not_checked("KYC", "KYC-AADHAAR", "Aadhaar offline verification", aadhaar, applicant.id))
    else:
        matches = name_similarity(aadhaar.response["name"], applicant.full_name) >= 90 and aadhaar.response["dob"] == str(applicant.dob)
        out.append(check("KYC", "KYC-AADHAAR", "Aadhaar offline verification", "PASS" if matches else "REFER",
                         "Name and date of birth match." if matches else "Name or date of birth differs from the application.", applicant.id,
                         {"masked_identifier": aadhaar.response["masked_identifier"], "mode": aadhaar.mode}))
    ckyc = call_for(calls, "ckyc", applicant.id)
    if ckyc is None or ckyc.response_status != "OK":
        out.append(not_checked("KYC", "KYC-CKYC", "CKYC registry search", ckyc, applicant.id))
    else:
        found = ckyc.response["record_found"]
        out.append(check("KYC", "KYC-CKYC", "CKYC registry search", "PASS", "An existing CKYC record was found." if found else "No existing CKYC record. Fresh KYC is relied on.", applicant.id,
                         {"record_found": found, "mode": ckyc.mode}))
    conflicts = [c for c in checklist.conflict_items(application, documents) if c["applicant_id"] in (applicant.id, None) and c["key"].startswith(("conflict:name", "conflict:pan", "conflict:dob"))]
    out.append(check("KYC", "KYC-DOC-CONSISTENCY", "Identity consistency across documents", "REFER" if conflicts else "PASS",
                     "; ".join(c["title"] for c in conflicts) if conflicts else "Name, PAN and date of birth agree across the documents provided.", applicant.id, {"conflicts": [c["evidence"] for c in conflicts]}))
    return out


def duplicate_check(db: Session, application: Application, applicant: Applicant) -> dict:
    others = db.execute(select(Application).join(Applicant).where(Applicant.pan == applicant.pan, Application.id != application.id,
                                                                  Application.status.in_(OPEN_STATUSES + ("APPROVED",)))).scalars().all()
    if others:
        return check("KYC", "KYC-DUPLICATE", "Duplicate applicant detection", "REFER", f"The same PAN appears on {len(others)} other live application(s).", applicant.id,
                     {"references": [o.reference for o in others]})
    return check("KYC", "KYC-DUPLICATE", "Duplicate applicant detection", "PASS", "No other live application carries this PAN.", applicant.id)


def aml_check(applicant: Applicant, calls: list[ProviderCall]) -> dict:
    call = call_for(calls, "sanctions", applicant.id)
    if call is None or call.response_status != "OK":
        return not_checked("AML", "AML-SCREEN", "Sanctions and PEP screening", call, applicant.id)
    candidates = call.response["candidates"]
    if not candidates:
        return check("AML", "AML-SCREEN", "Sanctions and PEP screening", "PASS", "No potential match on the synthetic watchlist.", applicant.id,
                     {"list_version": call.response["list_version"], "mode": call.mode})
    top = candidates[0]
    same_dob = top["dob"] == str(applicant.dob)
    if not same_dob and top["score"] < 95:
        return check("AML", "AML-SCREEN", "Sanctions and PEP screening", "FLAG",
                     f"Name resembles a watchlist entry ({top['list']}) but the date of birth differs. Kept as evidence for the reviewer.", applicant.id,
                     {"candidates": candidates, "classification": "NAME_ONLY", "list_version": call.response["list_version"], "mode": call.mode})
    return check("AML", "AML-SCREEN", "Sanctions and PEP screening", "REFER",
                 f"Potential match with a {top['list']} entry. This needs authorised AML review and is not a confirmed match.", applicant.id,
                 {"candidates": candidates, "classification": "POTENTIAL_MATCH", "list_version": call.response["list_version"], "mode": call.mode})


def doc_numbers(documents: list[Document], doc_type: str, applicant_id: int, name: str) -> float | None:
    fields = docs.field_map(documents, doc_type, applicant_id)
    field = fields.get(name)
    return field.effective_numeric if field else None


def fraud_check(applicant: Applicant, calls: list[ProviderCall], documents: list[Document], params: dict) -> dict:
    indicators = []
    for document in documents:
        if document.applicant_id not in (None, applicant.id):
            continue
        for finding in document.findings:
            if finding["id"] in ("DOC-UNCLASSIFIED", "DOC-LOW-CONFIDENCE", "DOC-TYPE-MISMATCH", "DOC-UNREADABLE", "DOC-BLURRY"):
                continue
            indicators.append({"code": finding["id"], "weight": SEVERITY_WEIGHT[finding["severity"]], "text": finding["text"], "document_id": document.id, "doc_type": document.doc_type})
    slip_net = doc_numbers(documents, "SALARY_SLIP", applicant.id, "net_pay")
    bank_call = call_for(calls, "account_aggregator", applicant.id)
    if slip_net and bank_call and bank_call.response_status == "OK" and bank_call.response["average_monthly_credit"] < slip_net * 0.85:
        indicators.append({"code": "FRAUD-INCOME-BANK", "weight": INDICATOR_WEIGHTS["income_vs_bank"], "document_id": None, "doc_type": "SALARY_SLIP",
                           "text": f"Average salary credits in the bank data ({bank_call.response['average_monthly_credit']:,.0f}) are well below the net pay on the salary slip ({slip_net:,.0f})."})
    slip_gross = doc_numbers(documents, "SALARY_SLIP", applicant.id, "gross")
    form16_gross = doc_numbers(documents, "FORM16", applicant.id, "gross")
    if slip_gross and form16_gross and abs(form16_gross / 12 - slip_gross) / slip_gross > 0.15:
        indicators.append({"code": "FRAUD-FORM16-SLIP", "weight": INDICATOR_WEIGHTS["form16_vs_slip"], "document_id": None, "doc_type": "FORM16",
                           "text": "Annual gross on Form 16 does not agree with the monthly gross on the salary slip."})
    if bank_call and bank_call.response_status == "OK" and bank_call.response["returned_cheques"] > 2:
        indicators.append({"code": "FRAUD-RETURNED-CHEQUES", "weight": INDICATOR_WEIGHTS["returned_cheques"], "document_id": None, "doc_type": "BANK_STATEMENT",
                           "text": f"{bank_call.response['returned_cheques']} returned cheques in the bank data."})
    bureau = call_for(calls, "bureau", applicant.id)
    if bureau and bureau.response_status == "OK":
        reported = bureau.response["reported_monthly_obligation"]
        if reported > applicant.existing_emi * 1.10 + 500:
            indicators.append({"code": "FRAUD-UNDISCLOSED-OBLIGATION", "weight": INDICATOR_WEIGHTS["undisclosed_obligation"], "document_id": None, "doc_type": None,
                               "text": f"The bureau shows monthly obligations of {reported:,.0f} against {applicant.existing_emi:,.0f} declared."})
    remaining = 1.0
    for item in indicators:
        remaining *= 1 - item["weight"]
    score = round(1 - remaining, 3)
    evidence = {"score": score, "indicators": indicators, "note": "Indicators suggest the need for review. They are not a finding of fraud."}
    if not indicators:
        return check("FRAUD", "FRAUD-INDICATORS", "Document and consistency indicators", "PASS", "No integrity or consistency indicators were raised.", applicant.id, evidence)
    status = "REFER" if score >= params["fraud_refer_score"] else "FLAG"
    return check("FRAUD", "FRAUD-INDICATORS", "Document and consistency indicators", status,
                 f"{len(indicators)} indicator(s) raised with a combined indicator score of {score:.2f}. This is a prompt for review and not a finding of fraud.", applicant.id, evidence)


def run_checks(db: Session, application: Application, params: dict) -> list[dict]:
    calls = latest_calls(db, application.id)
    documents = docs.active_documents(db, application.id)
    results = []
    for applicant in application.applicants:
        results += kyc_checks(application, applicant, calls, documents)
        results.append(duplicate_check(db, application, applicant))
        results.append(aml_check(applicant, calls))
        results.append(fraud_check(applicant, calls, documents, params))
    return results


def persist(db: Session, application: Application, results: list[dict], run: int) -> list[VerificationCheck]:
    rows = []
    for item in results:
        row = VerificationCheck(application_id=application.id, applicant_id=item["applicant_id"], category=item["category"], code=item["code"], title=item["title"],
                                status=item["status"], detail=item["detail"], evidence=item["evidence"], run=run)
        db.add(row)
        rows.append(row)
    db.flush()
    return rows
