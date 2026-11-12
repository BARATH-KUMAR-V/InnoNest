import copy

import pytest

from app.demo.scenarios import SCENARIOS
from app.services import policies
from app.services.engine import financials, rules

API = "/api/v1"


def latest(client, headers, app_id):
    return client.get(f"{API}/applications/{app_id}/decisions", headers=headers).json()[0]


def test_clean_applications_are_approved(client, run, underwriter):
    for key in ("clean_home_loan", "clean_lap"):
        application = run(key)
        assert application["status"] == "APPROVED"
        decision = latest(client, underwriter, application["id"])
        assert decision["outcome"] == "APPROVE" and decision["reason_codes"] == []


@pytest.mark.parametrize("key,expected_code", [("high_foir", "FOIR_LIMIT"), ("weak_credit", "CREDIT_SCORE_FLOOR")])
def test_policy_failures_are_rejected_with_reason_codes(client, run, underwriter, key, expected_code):
    application = run(key)
    assert application["status"] == "REJECTED"
    decision = latest(client, underwriter, application["id"])
    assert decision["outcome"] == "REJECT"
    assert expected_code in [r["code"] for r in decision["reason_codes"]]
    assert all(r["message"] for r in decision["reason_codes"])


@pytest.mark.parametrize("key,expected_code", [("aml_potential_match", "AML_REVIEW"), ("lap_encumbered", "PROPERTY_REVIEW"), ("tampered_slip", "FRAUD_INDICATORS_REVIEW")])
def test_exceptions_are_referred(client, run, underwriter, key, expected_code):
    application = run(key)
    assert application["status"] == "REFERRED"
    decision = latest(client, underwriter, application["id"])
    assert decision["outcome"] == "REFER"
    assert expected_code in [r["code"] for r in decision["reason_codes"]]


def test_decision_record_holds_everything_needed_to_audit_it(client, run, underwriter):
    application = run("clean_home_loan")
    decision = latest(client, underwriter, application["id"])
    assert decision["application_id"] == application["id"]
    assert decision["policy_key"] == "balanced" and decision["policy_version"] == 1
    assert decision["ruleset_version"] == policies.RULESET_VERSION
    assert len(decision["result_hash"]) == 64 and decision["created_at"]
    assert decision["explanation"].startswith("Outcome APPROVE under the Balanced policy, version 1")
    refs = {r["type"] for r in decision["evidence_refs"]}
    assert refs == {"document", "provider_call", "verification_check"}
    financial = decision["outputs"]["financial"]
    assert financial["inputs"]["loan_amount"] == 4_500_000
    assert financial["proposed_emi"] == pytest.approx(39_052.05, abs=0.01)
    assert financial["foir"] == pytest.approx((3000 + financial["proposed_emi"]) / 95000, abs=1e-3)
    assert financial["ltv"] == pytest.approx(0.75)
    assert financial["formulas"]["emi"]
    risk = decision["outputs"]["risk"]
    assert risk["band"] in "ABCDE" and risk["score"] == sum(c["points"] for c in risk["components"])
    assert "not a probability of default" in risk["disclosure"]
    assert decision["inputs"]["applicants"][0]["candidates"]["declared"] == 95000


def test_risk_scorecard_is_explainable_and_versioned(client, run, underwriter):
    application = run("clean_home_loan")
    risk = client.get(f"{API}/applications/{application['id']}/risk", headers=underwriter).json()
    assert risk["scorecard_version"] and {c["code"] for c in risk["components"]} == {"CREDIT_SCORE", "REPAYMENT", "INCOME_STABILITY", "OBLIGATIONS", "COLLATERAL", "EVIDENCE"}
    assert all(0 <= c["points"] <= c["max"] for c in risk["components"])
    assert risk["reason_codes"]


def test_decision_is_deterministic_and_replays_identically(client, run, underwriter):
    application = run("high_foir")
    decision = latest(client, underwriter, application["id"])
    replay = client.get(f"{API}/decisions/{decision['id']}/replay", headers=underwriter).json()
    assert replay["identical"] is True
    assert replay["recomputed_hash"] == decision["result_hash"]
    assert replay["recomputed_outcome"] == replay["stored_outcome"] == "REJECT"
    assert len(replay["steps"]) == 6


def test_same_application_gives_different_outcomes_under_each_policy(client, run, underwriter):
    application = run("high_foir")
    comparison = client.get(f"{API}/applications/{application['id']}/compare-policies", headers=underwriter).json()
    outcomes = {o["policy_key"]: o["outcome"] for o in comparison["outcomes"]}
    assert outcomes == {"balanced": "REJECT", "conservative": "REJECT", "flexible": "APPROVE"}
    changed = {d["code"]: d["by_policy"] for d in comparison["differences"]}
    assert changed["FOIR_LIMIT"]["balanced"]["outcome"] == "REJECT" and changed["FOIR_LIMIT"]["flexible"]["outcome"] == "PASS"
    assert "55%" in changed["FOIR_LIMIT"]["balanced"]["message"] and "65%" in changed["FOIR_LIMIT"]["flexible"]["message"]
    limits = {o["policy_key"]: o["foir_limit"] for o in comparison["outcomes"]}
    assert limits == {"balanced": 0.55, "conservative": 0.45, "flexible": 0.65}


def test_missing_information_never_produces_a_decision(client, run, underwriter):
    application = run("incomplete_application")
    assert application["status"] == "ACTION_REQUIRED"
    assert client.get(f"{API}/applications/{application['id']}/decisions", headers=underwriter).json() == []
    assert client.get(f"{API}/applications/{application['id']}/financial", headers=underwriter).status_code == 404


def test_policy_versions_are_stored_and_old_decisions_keep_their_version(client, run, auth):
    first = run("clean_home_loan")
    first_decision = latest(client, auth["underwriter"], first["id"])
    response = client.put(f"{API}/policies/balanced", headers=auth["policy_admin"], json={"params": {"foir_limit": {"SALARIED": 0.30, "GOVT": 0.60, "SELF_EMPLOYED": 0.50}}, "change_note": "Tighten salaried FOIR for testing"})
    assert response.status_code == 200 and response.json()["version"] == 2
    history = client.get(f"{API}/policies/balanced/history", headers=auth["underwriter"]).json()
    assert [(p["version"], p["status"]) for p in history] == [(2, "ACTIVE"), (1, "ARCHIVED")]
    assert history[0]["change_note"] == "Tighten salaried FOIR for testing"
    replay = client.get(f"{API}/decisions/{first_decision['id']}/replay", headers=auth["underwriter"]).json()
    assert replay["identical"] and replay["recomputed_outcome"] == "APPROVE"
    stricter = run("weak_credit")
    assert latest(client, auth["underwriter"], stricter["id"])["policy_version"] == 2


@pytest.mark.parametrize("params", [{"foir_limit": {"SALARIED": 1.5}}, {"credit_score": {"reject_below": 800, "refer_below": 700}}, {"tenure_limits_months": {"HOME_LOAN": [100, 50]}},
                                    {"ltv_limit": {"LAP": [[None, 0.99]]}}])
def test_invalid_policy_parameters_are_rejected(client, auth, params):
    response = client.put(f"{API}/policies/balanced", headers=auth["policy_admin"], json={"params": params, "change_note": "Invalid change attempt"})
    assert response.status_code == 422
    assert client.get(f"{API}/policies", headers=auth["underwriter"]).json()[0]["version"] == 1


def test_all_three_policies_are_labelled_illustrative(client, underwriter):
    listing = client.get(f"{API}/policies", headers=underwriter).json()
    assert [p["key"] for p in listing] == ["balanced", "conservative", "flexible"]
    assert all("Not a Hero Housing policy" in p["description"] for p in listing)


def test_boundary_values_in_the_rule_engine(client, run, underwriter):
    application = run("clean_home_loan")
    decision = latest(client, underwriter, application["id"])
    params = client.get(f"{API}/policies", headers=underwriter).json()[0]["params"]
    financial = copy.deepcopy(decision["outputs"]["financial"])
    risk = decision["outputs"]["risk"]
    snapshot = decision["inputs"]

    def outcome_of(code, **changes):
        updated = {**financial, **changes}
        return next(r["outcome"] for r in rules.evaluate(snapshot, updated, risk, params) if r["code"] == code)

    assert outcome_of("FOIR_LIMIT", foir=financial["foir_limit"]) == "PASS"
    assert outcome_of("FOIR_LIMIT", foir=financial["foir_limit"] + 0.0001) == "REJECT"
    assert outcome_of("LTV_LIMIT", ltv=financial["ltv_limit"]) == "PASS"
    assert outcome_of("LTV_LIMIT", ltv=financial["ltv_limit"] + 0.0001) == "REJECT"
    assert financials.ltv_limit_for(params["ltv_limit"]["HOME_LOAN"], 3_000_000) == 0.90
    assert financials.ltv_limit_for(params["ltv_limit"]["HOME_LOAN"], 3_000_001) == 0.80
    assert financials.ltv_limit_for(params["ltv_limit"]["HOME_LOAN"], 9_000_000) == 0.75


def test_referral_review_requires_note_and_records_a_second_decision(client, run, auth):
    referred = run("aml_potential_match")
    underwriter = auth["underwriter"]
    assert client.post(f"{API}/applications/{referred['id']}/review", headers=underwriter, json={"outcome": "APPROVE", "note": "short"}).status_code == 422
    response = client.post(f"{API}/applications/{referred['id']}/review", headers=underwriter, json={"outcome": "REJECT", "note": "Screening evidence could not be cleared"})
    assert response.status_code == 200 and response.json()["kind"] == "REVIEW" and response.json()["outcome"] == "REJECT"
    assert client.get(f"{API}/applications/{referred['id']}", headers=auth["applicant"]).json()["status"] == "REJECTED"
    assert len(client.get(f"{API}/applications/{referred['id']}/decisions", headers=underwriter).json()) == 2
    assert client.post(f"{API}/applications/{referred['id']}/review", headers=underwriter, json={"outcome": "APPROVE", "note": "Trying to review twice"}).status_code == 409


def test_cleared_check_lets_a_reevaluation_approve(client, run, auth):
    referred = run("aml_potential_match")
    underwriter = auth["underwriter"]
    check = next(c for c in client.get(f"{API}/applications/{referred['id']}/verification", headers=underwriter).json() if c["code"] == "AML-SCREEN")
    assert client.post(f"{API}/applications/{referred['id']}/verification/{check['id']}/disposition", headers=underwriter, json={"disposition": "CLEARED", "note": "Date of birth and address differ from the listed person"}).status_code == 200
    assert client.post(f"{API}/applications/{referred['id']}/reevaluate", headers=underwriter).json()["status"] == "APPROVED"
    check_after = next(c for c in client.get(f"{API}/applications/{referred['id']}/verification", headers=underwriter).json() if c["code"] == "AML-SCREEN")
    assert check_after["status"] == "REFER" and check_after["disposition"] == "CLEARED"


def test_property_assessment_does_not_claim_title(client, run, underwriter):
    referred = run("lap_encumbered")
    prop = client.get(f"{API}/applications/{referred['id']}/property", headers=underwriter).json()
    codes = {c["code"]: c for c in prop["checks"]}
    assert codes["PROP-ENCUMBRANCE"]["status"] == "REFER" and len(codes["PROP-ENCUMBRANCE"]["evidence"]["charges"]) == 2
    assert codes["PROP-OWNER-APPLICANT"]["status"] == "PASS"
    assert "does not establish legal title" in prop["legal_title_note"]


def test_financial_view_shows_inputs_and_income_basis(client, run, underwriter):
    application = run("clean_home_loan")
    view = client.get(f"{API}/applications/{application['id']}/financial", headers=underwriter).json()
    assert view["financial"]["max_eligible_emi"] > 0 and view["financial"]["indicative_eligible_loan"] > 0
    assert view["income"][0]["basis"] in view["income"][0]["candidates"]


def test_evidence_graph_links_documents_providers_calculations_and_reasons(client, run, underwriter):
    application = run("high_foir")
    graph = client.get(f"{API}/applications/{application['id']}/evidence-graph", headers=underwriter).json()
    kinds = {n["type"] for n in graph["nodes"]}
    assert {"APPLICATION", "APPLICANT", "DOCUMENT", "FIELD", "PROVIDER_RESPONSE", "VERIFICATION", "CALCULATION", "POLICY", "DECISION", "REASON"} <= kinds
    ids = {n["id"] for n in graph["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in graph["edges"])
    slim = client.get(f"{API}/applications/{application['id']}/evidence-graph", headers=underwriter, params={"include_fields": "false"}).json()
    assert "FIELD" not in {n["type"] for n in slim["nodes"]}


def test_calculation_endpoints_validate_and_compute(client, applicant):
    emi = client.post(f"{API}/calculations/emi", headers=applicant, json={"principal": 5_000_000, "annual_rate": 8.5, "months": 240}).json()
    assert emi["emi"] == pytest.approx(43391.16, abs=0.01) and len(emi["schedule_preview"]) == 12
    assert client.post(f"{API}/calculations/emi", headers=applicant, json={"principal": 5_000_000, "annual_rate": 8.5, "months": 0}).status_code == 422
    zero = client.post(f"{API}/calculations/emi", headers=applicant, json={"principal": 1_200_000, "annual_rate": 0, "months": 120}).json()
    assert zero["emi"] == 10000.0 and zero["total_interest"] == 0
    eligibility = client.post(f"{API}/calculations/eligibility", headers=applicant, json={"product": "HOME_LOAN", "employment_type": "SALARIED", "monthly_income": 100000, "existing_emi": 10000,
                                                                                         "interest_rate": 8.5, "tenure_months": 240, "property_value": 6000000, "loan_amount": 4000000}).json()
    assert eligibility["max_eligible_emi"] == 45000.0 and eligibility["ltv"] == pytest.approx(0.6667, abs=1e-3)
    assert eligibility["indicative_eligible_loan"] == min(eligibility["loan_by_foir"], eligibility["loan_by_ltv"])
