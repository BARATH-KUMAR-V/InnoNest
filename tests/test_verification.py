import copy
from datetime import date

import pytest

from app.core.config import settings
from app.demo import runner
from app.demo.scenarios import SCENARIOS, Scenario
from app.providers.adapters import ADAPTERS, name_similarity
from app.providers.base import ProviderRequest

API = "/api/v1"
ENVELOPE = {"provider", "provider_name", "mode", "integration_status", "consent_ref", "response", "response_status", "source_ref", "verification_result", "requested_at", "response_hash"}


def checks(client, headers, app_id):
    return {(c["code"], c["applicant_id"]): c for c in client.get(f"{API}/applications/{app_id}/verification", headers=headers).json()}


def by_code(client, headers, app_id):
    return {c["code"]: c for c in client.get(f"{API}/applications/{app_id}/verification", headers=headers).json()}


def test_every_provider_response_carries_the_full_envelope(client, run, underwriter):
    approved = run("clean_home_loan")
    calls = client.get(f"{API}/applications/{approved['id']}/provider-calls", headers=underwriter).json()
    assert {c["provider"] for c in calls} == set(ADAPTERS)
    for call in calls:
        assert ENVELOPE <= set(call)
        assert call["mode"] in ("MOCK", "SANDBOX", "LIVE_PARTNER")
        assert call["requested_at"] and call["response_status"] == "OK"
    assert not any(c["mode"] == "LIVE_PARTNER" for c in calls)
    consented = [c for c in calls if ADAPTERS[c["provider"]].needs_consent]
    assert all(c["consent_ref"] and c["consent_ref"].startswith("CNS-") for c in consented)
    assert all(c["source_ref"] for c in calls)


def test_integrations_never_claim_to_be_live(client, underwriter):
    listing = client.get(f"{API}/integrations", headers=underwriter).json()
    assert len(listing) == 11
    assert all(i["live"] is False for i in listing)
    assert {i["mode"] for i in listing} <= {"MOCK", "SANDBOX"}
    assert all(i["mode_note"] for i in listing)


def test_provider_without_consent_does_not_run():
    adapter = ADAPTERS["bureau"]
    person = {"pan": "ASHPR1234A", "full_name": "Priya Raman", "dob": date(1990, 3, 14), "existing_emi": 0}
    result = adapter.call(ProviderRequest({"reference": "X", "survey_no": "1"}, person, None))
    assert result["response_status"] == "CONSENT_MISSING"
    assert result["verification_result"] == "NOT_CHECKED"
    assert result["payload"] == {}


def test_live_partner_mode_without_credentials_never_fakes_success(monkeypatch):
    monkeypatch.setattr(settings, "provider_modes", '{"bureau": "LIVE_PARTNER"}')
    person = {"pan": "ASHPR1234A", "full_name": "Priya Raman", "dob": date(1990, 3, 14), "existing_emi": 0}
    result = ADAPTERS["bureau"].call(ProviderRequest({"reference": "X", "survey_no": "1"}, person, "CNS-X"))
    assert result["mode"] == "LIVE_PARTNER"
    assert result["response_status"] == "UNAVAILABLE" and result["integration_status"] == "NOT_CONFIGURED"
    assert result["verification_result"] == "NOT_CHECKED"


def test_provider_outage_holds_the_application_instead_of_deciding(client, run, auth):
    client.post(f"{API}/integrations/bureau/outage", headers=auth["underwriter"], json={"down": True})
    held = run("clean_home_loan")
    assert held["status"] == "VERIFICATION_PENDING" and held["pending_stage"] == "VERIFICATION"
    assert client.get(f"{API}/applications/{held['id']}/decisions", headers=auth["underwriter"]).json() == []
    assert client.post(f"{API}/applications/{held['id']}/retry-verification", headers=auth["underwriter"]).status_code == 200
    still = client.get(f"{API}/applications/{held['id']}", headers=auth["applicant"]).json()
    assert still["status"] == "VERIFICATION_PENDING"
    client.post(f"{API}/integrations/bureau/outage", headers=auth["underwriter"], json={"down": False})
    client.post(f"{API}/applications/{held['id']}/retry-verification", headers=auth["underwriter"])
    resumed = client.get(f"{API}/applications/{held['id']}", headers=auth["applicant"]).json()
    assert resumed["status"] == "APPROVED"


def test_clean_application_passes_identity_checks(client, run, underwriter):
    approved = run("clean_home_loan")
    result = by_code(client, underwriter, approved["id"])
    for code in ("KYC-PAN", "KYC-AADHAAR", "KYC-CKYC", "KYC-DOC-CONSISTENCY", "KYC-DUPLICATE", "AML-SCREEN", "FRAUD-INDICATORS"):
        assert result[code]["status"] == "PASS", code
    assert {c["status"] for c in result.values()} <= {"PASS", "FLAG", "REFER", "FAIL", "NOT_CHECKED"}


def test_small_name_difference_on_pan_is_a_flag_not_a_referral(client, run, underwriter):
    approved = run("incomplete_application")
    from app.demo.runner import upload
    from app.demo.scenarios import generate_documents
    ids = [a["id"] for a in approved["applicants"]]
    for item in generate_documents(SCENARIOS["incomplete_application"], ["SALARY_SLIP", "BANK_STATEMENT"]):
        upload(client, runner.login(client, "applicant@example.com", "Applicant@123"), approved["id"], ids, item)
    result = by_code(client, underwriter, approved["id"])
    assert result["KYC-PAN"]["status"] == "FLAG"
    assert result["KYC-PAN"]["evidence"]["registry_name"] == "LAKSHMI VENKATESH"


def test_potential_aml_match_is_referred_for_review(client, run, underwriter):
    referred = run("aml_potential_match")
    assert referred["status"] == "REFERRED"
    aml = by_code(client, underwriter, referred["id"])["AML-SCREEN"]
    assert aml["status"] == "REFER"
    assert aml["evidence"]["classification"] == "POTENTIAL_MATCH"
    assert "not a confirmed match" in aml["detail"]
    codes = [r["code"] for r in client.get(f"{API}/applications/{referred['id']}/decisions", headers=underwriter).json()[0]["reason_codes"]]
    assert codes == ["AML_REVIEW"]


def test_name_only_similarity_is_flagged_but_not_referred(client, auth, underwriter):
    body = copy.deepcopy(SCENARIOS["clean_home_loan"].application)
    body["applicants"][0].update(full_name="Rohan Mehra Nair", pan="KLMNO4321P", dob="1985-02-02")
    scenario = Scenario("custom", "custom", "", "", body)
    submitted = runner.run_scenario_object(client, auth["applicant"], scenario)
    aml = by_code(client, underwriter, submitted["id"])["AML-SCREEN"]
    assert aml["status"] == "FLAG"
    assert aml["evidence"]["classification"] == "NAME_ONLY"


def test_tampered_salary_slip_is_referred_with_indicators_not_rejected(client, run, underwriter):
    referred = run("tampered_slip")
    assert referred["status"] == "REFERRED"
    fraud = by_code(client, underwriter, referred["id"])["FRAUD-INDICATORS"]
    assert fraud["status"] == "REFER"
    codes = {i["code"] for i in fraud["evidence"]["indicators"]}
    assert {"DOC-FONT-MISMATCH", "FRAUD-INCOME-BANK"} <= codes
    assert fraud["evidence"]["score"] >= 0.35
    assert "not a finding of fraud" in fraud["detail"]
    assert "confirmed" not in fraud["detail"].lower()


def test_duplicate_pan_on_another_live_application_is_referred(client, run, underwriter):
    run("clean_home_loan")
    second = run("clean_home_loan")
    assert second["status"] == "REFERRED"
    duplicate = by_code(client, underwriter, second["id"])["KYC-DUPLICATE"]
    assert duplicate["status"] == "REFER" and duplicate["evidence"]["references"]


def test_name_similarity_is_tolerant_of_honorifics_and_case():
    assert name_similarity("Mr. Priya Raman", "PRIYA RAMAN") >= 97
    assert name_similarity("Priya Raman", "Karthik Subramanian") < 60
