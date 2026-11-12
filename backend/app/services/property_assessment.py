from app.models import Application, Document, ProviderCall
from app.providers.adapters import name_similarity
from app.services import documents as docs
from app.services.verification import call_for

TITLE_NOTE = "Text extraction from a document does not establish legal title. Title is confirmed only through the lender's legal opinion."


def entry(code: str, title: str, status: str, detail: str, evidence: dict | None = None) -> dict:
    return {"code": code, "title": title, "status": status, "detail": detail, "evidence": evidence or {}}


def assess(application: Application, calls: list[ProviderCall], documents: list[Document], params: dict) -> dict:
    checks = []
    names = [a.full_name for a in application.applicants]
    registration = call_for(calls, "property_registration", None)
    cersai = call_for(calls, "cersai", None)
    deed = docs.field_map(documents, "SALE_DEED")
    agreement = docs.field_map(documents, "SALE_AGREEMENT")
    valuation = docs.field_map(documents, "VALUATION_REPORT")
    encumbrance = docs.field_map(documents, "ENCUMBRANCE_CERTIFICATE")
    legal = docs.field_map(documents, "LEGAL_REPORT")
    technical = docs.field_map(documents, "TECHNICAL_REPORT")

    owner_claim = application.owner_name or ""
    if application.product == "LAP":
        ok = any(name_similarity(owner_claim, n) >= 85 for n in names)
        checks.append(entry("PROP-OWNER-APPLICANT", "Owner matches an applicant", "PASS" if ok else "REFER",
                            "The property owner is one of the applicants." if ok else "The property owner is not an applicant. Third-party property needs reviewer approval.", {"owner": owner_claim, "applicants": names}))
    elif agreement.get("seller") and application.seller_name:
        ok = name_similarity(agreement["seller"].effective_value, application.seller_name) >= 85
        checks.append(entry("PROP-SELLER", "Seller on agreement matches application", "PASS" if ok else "REFER",
                            "Seller name agrees." if ok else "Seller name on the agreement differs from the application.", {"agreement": agreement["seller"].effective_value, "application": application.seller_name}))
    if registration and registration.response_status == "OK":
        registered = registration.response["registered_owner"]
        ok = name_similarity(registered, owner_claim or names[0]) >= 85 and not registration.response["title_gap"]
        checks.append(entry("PROP-REGISTRY-OWNER", "Registered owner in registration records", "PASS" if ok else "REFER",
                            "Registration records agree with the declared owner." if ok else "Registration records show a different owner or a gap in the title chain.",
                            {"registered_owner": registered, "declared_owner": owner_claim, "title_gap": registration.response["title_gap"], "source_ref": registration.source_ref, "mode": registration.mode}))
    else:
        checks.append(entry("PROP-REGISTRY-OWNER", "Registered owner in registration records", "NOT_CHECKED", "The registration lookup did not return a result."))
    surveys = {t: f["survey_no"].effective_value.strip().lower() for t, f in (("SALE_DEED", deed), ("SALE_AGREEMENT", agreement), ("VALUATION_REPORT", valuation), ("ENCUMBRANCE_CERTIFICATE", encumbrance), ("LEGAL_REPORT", legal), ("TECHNICAL_REPORT", technical)) if "survey_no" in f}
    consistent = all(v == application.survey_no.strip().lower() for v in surveys.values())
    checks.append(entry("PROP-IDENTIFICATION", "Property identified consistently", "PASS" if consistent and surveys else ("REFER" if surveys else "NOT_CHECKED"),
                        "The survey number agrees across the property documents." if consistent and surveys else ("The survey number differs between documents." if surveys else "No property document carried a survey number."), {"survey_numbers": surveys}))
    disallowed = application.property_type in params["disallowed_property_types"][application.product]
    checks.append(entry("PROP-TYPE", "Property type is acceptable", "FAIL" if disallowed else "PASS",
                        f"{application.property_type.replace('_', ' ').title()} is not accepted for this product." if disallowed else "The property type is acceptable under the policy.", {"property_type": application.property_type, "city": application.property_city}))
    declared = float(application.declared_value)
    assessed = valuation["market_value"].effective_numeric if "market_value" in valuation else None
    deviation = (declared - assessed) / declared if assessed and declared else None
    if assessed is None:
        checks.append(entry("PROP-VALUATION", "Declared value against valuation", "NOT_CHECKED", "No valuation figure could be read."))
    else:
        limit = params["valuation_deviation_refer_pct"]
        status = "PASS" if deviation <= limit else "REFER"
        checks.append(entry("PROP-VALUATION", "Declared value against valuation", status,
                            f"Declared value is {deviation * 100:.1f}% above the valuation." if deviation > 0 else f"Valuation is {abs(deviation) * 100:.1f}% above the declared value.",
                            {"declared": declared, "valuation": assessed, "deviation_pct": round(deviation, 4), "limit_pct": limit}))
    charges = []
    if "subsisting_charge" in encumbrance:
        charges.append({"source": "ENCUMBRANCE_CERTIFICATE", "text": encumbrance["subsisting_charge"].effective_value})
    if cersai and cersai.response_status == "OK" and cersai.response["charge_found"]:
        charges += [{"source": "CERSAI", **c} for c in cersai.response["charges"]]
    if charges:
        checks.append(entry("PROP-ENCUMBRANCE", "Existing mortgage or charge", "REFER", "A subsisting charge is recorded against the property. Release or settlement needs review.", {"charges": charges}))
    elif cersai and cersai.response_status != "OK":
        checks.append(entry("PROP-ENCUMBRANCE", "Existing mortgage or charge", "NOT_CHECKED", "The security interest search did not return a result."))
    else:
        checks.append(entry("PROP-ENCUMBRANCE", "Existing mortgage or charge", "PASS", "No subsisting charge was found in the certificate or the security interest search."))
    if legal:
        clear = "clear" in legal.get("title_opinion", type("v", (), {"effective_value": ""})).effective_value.lower() and legal.get("litigation") and legal["litigation"].effective_value.strip().upper() == "NIL"
        checks.append(entry("PROP-LEGAL", "Legal opinion", "PASS" if clear else "REFER", "The legal opinion records a clear title and no litigation." if clear else "The legal opinion records an adverse point or litigation.",
                            {"title_opinion": legal.get("title_opinion").effective_value if legal.get("title_opinion") else None, "note": TITLE_NOTE}))
    else:
        checks.append(entry("PROP-LEGAL", "Legal opinion", "NOT_CHECKED" if application.loan_amount < params["extra_reports_required_above"][application.product] else "REFER", "No legal opinion has been read for this application.", {"note": TITLE_NOTE}))
    if technical:
        sound = technical.get("structural_condition") and technical["structural_condition"].effective_value.strip().lower() == "satisfactory"
        checks.append(entry("PROP-TECHNICAL", "Technical inspection", "PASS" if sound else "REFER", "The technical report records a satisfactory condition." if sound else "The technical report records a condition that needs review."))
    else:
        checks.append(entry("PROP-TECHNICAL", "Technical inspection", "NOT_CHECKED", "No technical inspection report has been read."))
    accepted = min(declared, assessed) if assessed else declared
    return {"checks": checks, "declared_value": declared, "valuation_value": assessed, "accepted_value": accepted, "deviation_pct": round(deviation, 4) if deviation is not None else None,
            "existing_mortgage_amount": float(application.existing_mortgage_amount), "legal_title_note": TITLE_NOTE}
