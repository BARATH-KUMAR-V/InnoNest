from datetime import date

from rapidfuzz import fuzz

from app.providers import sandbox_data as data
from app.providers.base import Adapter, ProviderRequest, stable_random

HONORIFICS = {"MR", "MRS", "MS", "SHRI", "SMT", "DR"}


def normalise_name(name: str) -> str:
    tokens = name.upper().replace(".", " ").split()
    return " ".join(token for token in tokens if token not in HONORIFICS)


def name_similarity(first: str, second: str) -> float:
    a, b = normalise_name(first), normalise_name(second)
    return max(fuzz.token_sort_ratio(a, b), fuzz.WRatio(a, b) - 4)


class PanAdapter(Adapter):
    key = "pan"
    name = "PAN verification"
    default_mode = "MOCK"
    live_route = "Income Tax Department approved PAN verification route"
    consent_scope = "PAN verification"

    def fetch(self, request):
        applicant = request.applicant
        entry = data.profile_for(applicant["pan"])
        registry_name = entry.get("pan_registry_name") or entry.get("name") or applicant["full_name"]
        registry_dob = entry.get("dob") or applicant["dob"]
        valid_format = len(applicant["pan"]) == 10 and applicant["pan"][:5].isalpha() and applicant["pan"][5:9].isdigit()
        return {"pan": applicant["pan"], "format_valid": valid_format, "registry_name": registry_name.upper(), "registry_dob": str(registry_dob),
                "status": "ACTIVE", "aadhaar_linked": True}

    def verify(self, payload, request):
        if not payload["format_valid"]:
            return "NOT_FOUND"
        similarity = name_similarity(payload["registry_name"], request.applicant["full_name"])
        if payload["registry_dob"] != str(request.applicant["dob"]) or similarity < 85:
            return "MISMATCH"
        return "VERIFIED" if similarity >= 97 else "PARTIAL"


class CkycAdapter(Adapter):
    key = "ckyc"
    name = "CKYC registry search"
    default_mode = "MOCK"
    live_route = "Central KYC Records Registry search and download for reporting entities"
    consent_scope = "CKYC record retrieval"

    def fetch(self, request):
        found = stable_random("ckyc", request.applicant["pan"]).random() < 0.6
        return {"record_found": found, "ckyc_identifier": ("5000" + request.applicant["pan"][5:9] + "7710") if found else None, "kyc_level": "FULL" if found else None}

    def verify(self, payload, request):
        return "VERIFIED" if payload["record_found"] else "NOT_FOUND"


class AadhaarAdapter(Adapter):
    key = "aadhaar"
    name = "Aadhaar offline verification (authorised route)"
    default_mode = "SANDBOX"
    live_route = "UIDAI offline e-KYC through an authorised partner with explicit applicant consent"
    consent_scope = "Aadhaar offline e-KYC"

    def fetch(self, request):
        applicant = request.applicant
        rng = stable_random("aadhaar", applicant["pan"])
        return {"xml_signature_valid": True, "share_code_valid": True, "name": applicant["full_name"], "dob": str(applicant["dob"]),
                "address": applicant.get("address") or "", "masked_identifier": "XXXX XXXX " + str(rng.randint(1000, 9999)), "generated_within_days": 2}

    def verify(self, payload, request):
        return "VERIFIED" if payload["xml_signature_valid"] and payload["share_code_valid"] else "MISMATCH"


class DigilockerAdapter(Adapter):
    key = "digilocker"
    name = "DigiLocker issued documents"
    default_mode = "MOCK"
    live_route = "DigiLocker requester API with the applicant's authorisation"
    consent_scope = "DigiLocker document fetch"

    def fetch(self, request):
        return {"documents": [{"type": "PAN", "issuer": "Income Tax Department", "uri": f"in.gov.pan-{request.applicant['pan'][5:9]}"},
                              {"type": "IDENTITY", "issuer": "UIDAI", "uri": "in.gov.uidai-demo"}]}

    def verify(self, payload, request):
        return "VERIFIED" if payload["documents"] else "NOT_FOUND"


class BureauAdapter(Adapter):
    key = "bureau"
    name = "Credit bureau report"
    default_mode = "SANDBOX"
    live_route = "Credit information company member API"
    consent_scope = "Credit report pull"

    def fetch(self, request):
        applicant = request.applicant
        profile = data.bureau_profile(applicant)
        existing = float(applicant.get("existing_emi") or 0)
        accounts = [{"type": "RETAIL LOAN", "lender": "Member institution (synthetic)", "emi": existing, "dpd": profile["max_dpd_12m"], "open": True}] if existing else []
        return {"score": profile["score"], "max_dpd_12m": profile["max_dpd_12m"], "enquiries_6m": profile["enquiries_6m"],
                "utilization": profile["utilization"], "active_accounts": accounts, "reported_monthly_obligation": existing,
                "report_date": date.today().isoformat()}

    def verify(self, payload, request):
        return "VERIFIED" if payload["score"] else "PARTIAL"


class AccountAggregatorAdapter(Adapter):
    key = "account_aggregator"
    name = "Account Aggregator bank statement"
    default_mode = "SANDBOX"
    live_route = "RBI-licensed Account Aggregator with the lender as financial information user"
    consent_scope = "Bank statement for 6 months"

    def fetch(self, request):
        applicant = request.applicant
        profile = data.bank_profile(applicant)
        rng = stable_random("bank", applicant["pan"])
        salaried = applicant["employment_type"] in ("SALARIED", "GOVT")
        base = float(applicant["monthly_income"]) if salaried else float(applicant.get("annual_turnover") or applicant["monthly_income"] * 12) / 12
        months, credits, balance = [], [], 120000.0
        for start in data.month_starts(6, date.today()):
            credit = base * profile["income_factor"] * (1 + (rng.uniform(-0.01, 0.01) if salaried else rng.gauss(0, profile["income_cv"])))
            credit = round(credit, 2)
            debit = round(float(applicant["monthly_income"]) * 0.45 + float(applicant.get("existing_emi") or 0), 2)
            balance += credit - debit
            months.append({"month": start.strftime("%Y-%m"), "total_credits": credit, "total_debits": debit, "closing_balance": round(balance, 2)})
            credits.append(credit)
        return {"institution": "Sample Bank (synthetic FIP)", "account_masked": "XXXXXX" + applicant["pan"][-4:], "months": months,
                "average_monthly_credit": round(sum(credits) / len(credits), 2), "average_balance": round(sum(m["closing_balance"] for m in months) / 6, 2),
                "returned_cheques": profile["bounces"], "emi_debits_detected": float(applicant.get("existing_emi") or 0)}

    def verify(self, payload, request):
        return "VERIFIED"


class GstAdapter(Adapter):
    key = "gst"
    name = "GST returns"
    default_mode = "MOCK"
    live_route = "GST suvidha provider with taxpayer consent"
    consent_scope = "GST return data"

    def fetch(self, request):
        applicant = request.applicant
        turnover = applicant.get("annual_turnover")
        if applicant["employment_type"] != "SELF_EMPLOYED" or not turnover:
            return {"applicable": False}
        rng = stable_random("gst", applicant["pan"])
        monthly = float(turnover) / 12
        return {"applicable": True, "gstin_masked": "33XXXXX" + applicant["pan"][5:9] + "1Z5", "filing_regular": True,
                "monthly_turnover": [round(monthly * (1 + rng.uniform(-0.12, 0.12)), 0) for _ in range(12)]}

    def verify(self, payload, request):
        return "VERIFIED" if payload.get("applicable") else "NOT_CHECKED"


class ItrAdapter(Adapter):
    key = "itr"
    name = "Income tax return data"
    default_mode = "MOCK"
    live_route = "Income Tax e-filing data via approved route with taxpayer consent"
    consent_scope = "ITR data"

    def fetch(self, request):
        applicant = request.applicant
        declared = applicant.get("annual_itr_income") or float(applicant["monthly_income"]) * 12
        factor = stable_random("itr", applicant["pan"]).uniform(0.98, 1.0)
        return {"assessment_year": "2026-27", "gross_total_income": round(float(declared) * factor, 0), "filed_on_time": True}

    def verify(self, payload, request):
        return "VERIFIED"


class CersaiAdapter(Adapter):
    key = "cersai"
    name = "CERSAI security interest search"
    default_mode = "SANDBOX"
    needs_consent = False
    live_route = "CERSAI public search or lender filing access"

    def fetch(self, request):
        charge = data.profile_for(request.applicant["pan"]).get("cersai_charge")
        return {"search_basis": "PROPERTY_AND_OWNER", "charge_found": bool(charge), "charges": [charge] if charge else []}

    def verify(self, payload, request):
        return "FLAGGED" if payload["charge_found"] else "VERIFIED"


class PropertyRegistrationAdapter(Adapter):
    key = "property_registration"
    name = "Property registration records"
    default_mode = "MOCK"
    needs_consent = False
    live_route = "State land record and registration portals or an authorised data partner"

    def fetch(self, request):
        application = request.application
        entry = data.profile_for(request.applicant["pan"])
        owner = entry.get("registrar_owner") or application.get("owner_name") or request.applicant["full_name"]
        return {"registered_owner": owner, "survey_no": application["survey_no"], "last_registration_year": 2019,
                "title_chain": [{"from": "Original allottee", "to": owner, "year": 2019, "instrument": "Sale deed"}], "title_gap": bool(entry.get("title_gap", False))}

    def verify(self, payload, request):
        expected = request.application.get("owner_name") or request.applicant["full_name"]
        return "VERIFIED" if name_similarity(payload["registered_owner"], expected) >= 85 and not payload["title_gap"] else "MISMATCH"


class SanctionsAdapter(Adapter):
    key = "sanctions"
    name = "Sanctions and PEP screening (synthetic watchlist)"
    default_mode = "SANDBOX"
    needs_consent = False
    live_route = "Commercial sanctions and PEP list provider"

    def fetch(self, request):
        query = request.applicant["full_name"]
        matches = []
        for entry in data.watchlist():
            score = name_similarity(query, entry["name"])
            if score >= 80:
                matches.append({"name": entry["name"], "dob": entry["dob"], "list": entry["list"], "country": entry["country"], "score": round(score, 1), "note": entry["note"]})
        return {"screened_name": query, "list_version": "synthetic-watchlist-2026-11", "candidates": sorted(matches, key=lambda m: -m["score"])}

    def verify(self, payload, request):
        return "POTENTIAL_MATCH" if payload["candidates"] else "VERIFIED"


ADAPTERS: dict[str, Adapter] = {adapter.key: adapter for adapter in (
    PanAdapter(), CkycAdapter(), AadhaarAdapter(), DigilockerAdapter(), BureauAdapter(), AccountAggregatorAdapter(),
    GstAdapter(), ItrAdapter(), CersaiAdapter(), PropertyRegistrationAdapter(), SanctionsAdapter())}
