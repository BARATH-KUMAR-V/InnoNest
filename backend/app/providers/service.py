from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Applicant, Application, ProviderCall
from app.providers.adapters import ADAPTERS
from app.providers.base import OUTAGES, ProviderRequest, content_hash

CONSENT_SCOPE = {"pan": "kyc", "ckyc": "kyc", "aadhaar": "kyc", "digilocker": "kyc", "bureau": "credit_bureau",
                 "account_aggregator": "bank_statement", "gst": "bank_statement", "itr": "bank_statement"}
APPLICANT_PROVIDERS = ("pan", "ckyc", "aadhaar", "digilocker", "sanctions", "bureau", "account_aggregator", "gst", "itr")
APPLICATION_PROVIDERS = ("cersai", "property_registration")
CRITICAL_PROVIDERS = ("pan", "bureau", "account_aggregator", "sanctions", "property_registration", "cersai")


def application_view(application: Application) -> dict:
    return {"reference": application.reference, "survey_no": application.survey_no, "owner_name": application.owner_name, "declared_value": application.declared_value,
            "property_city": application.property_city, "product": application.product}


def applicant_view(applicant: Applicant) -> dict:
    return {"id": applicant.id, "pan": applicant.pan, "full_name": applicant.full_name, "dob": applicant.dob, "employment_type": applicant.employment_type,
            "monthly_income": applicant.monthly_income, "existing_emi": applicant.existing_emi, "address": applicant.address, "annual_turnover": applicant.annual_turnover,
            "annual_itr_income": applicant.annual_itr_income}


def consent_reference(application: Application, key: str) -> str | None:
    scope = CONSENT_SCOPE.get(key)
    if scope is None or (application.consents or {}).get(scope):
        return f"CNS-{application.reference}-{scope or 'none'}".upper()
    return None


def next_run(db: Session, application_id: int) -> int:
    latest = db.execute(select(func.max(ProviderCall.run)).where(ProviderCall.application_id == application_id)).scalar()
    return (latest or 0) + 1


def call_provider(db: Session, application: Application, applicant: Applicant, key: str, run: int) -> ProviderCall:
    adapter = ADAPTERS[key]
    request = ProviderRequest(application_view(application), applicant_view(applicant), consent_reference(application, key))
    envelope = adapter.call(request)
    row = ProviderCall(application_id=application.id, applicant_id=applicant.id, provider=key, provider_name=envelope["provider_name"], mode=envelope["mode"],
                       integration_status=envelope["integration_status"], response_status=envelope["response_status"], consent_ref=envelope["consent_ref"],
                       source_ref=envelope["source_ref"], verification_result=envelope["verification_result"], response=envelope["payload"],
                       response_hash=content_hash(envelope["payload"]), run=run)
    db.add(row)
    db.flush()
    return row


def collect(db: Session, application: Application, run: int) -> list[ProviderCall]:
    calls = []
    for applicant in application.applicants:
        for key in APPLICANT_PROVIDERS:
            calls.append(call_provider(db, application, applicant, key, run))
    primary = application.applicants[0]
    for key in APPLICATION_PROVIDERS:
        calls.append(call_provider(db, application, primary, key, run))
    return calls


def latest_calls(db: Session, application_id: int) -> list[ProviderCall]:
    last_ok: dict[tuple, ProviderCall] = {}
    for call in db.execute(select(ProviderCall).where(ProviderCall.application_id == application_id).order_by(ProviderCall.id)).scalars():
        key = (call.provider, call.applicant_id if call.provider in APPLICANT_PROVIDERS else None)
        if call.response_status == "OK" or key not in last_ok or last_ok[key].response_status != "OK":
            last_ok[key] = call
    return list(last_ok.values())


def unavailable_critical(calls: list[ProviderCall]) -> list[ProviderCall]:
    return [c for c in calls if c.provider in CRITICAL_PROVIDERS and c.response_status in ("UNAVAILABLE", "FAILED")]


def set_outage(key: str, down: bool) -> None:
    if down:
        OUTAGES.add(key)
    else:
        OUTAGES.discard(key)
