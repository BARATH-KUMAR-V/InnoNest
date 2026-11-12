import copy

import pytest

from app.demo.scenarios import SCENARIOS

API = "/api/v1"


def payload(key="clean_home_loan"):
    return copy.deepcopy(SCENARIOS[key].application)


def test_create_application_starts_as_draft_with_reference(client, applicant):
    response = client.post(f"{API}/applications", headers=applicant, json=payload())
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["reference"].startswith("INN-")
    assert body["applicants"][0]["pan"] == "ASHPR1234A"
    assert body["policy_key"] == "balanced"


def test_create_lap_with_joint_applicant(client, applicant):
    body = payload("clean_lap")
    body["applicants"].append({**body["applicants"][0], "role": "CO_APPLICANT", "full_name": "Co Applicant", "pan": "ZZZZZ9999Z", "email": "co.applicant@example.com"})
    response = client.post(f"{API}/applications", headers=applicant, json=body)
    assert response.status_code == 201
    assert [a["role"] for a in response.json()["applicants"]] == ["PRIMARY", "CO_APPLICANT"]


@pytest.mark.parametrize("field,value", [("loan_amount", 0), ("loan_amount", -100), ("interest_rate", 55), ("interest_rate", -1), ("tenure_months", 0), ("tenure_months", 600),
                                         ("declared_value", 0), ("product", "PERSONAL_LOAN"), ("property_pincode", "12AB")])
def test_invalid_application_fields_return_field_errors(client, applicant, field, value):
    body = payload()
    body[field] = value
    response = client.post(f"{API}/applications", headers=applicant, json=body)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert any(field in d["field"] for d in error["details"])


@pytest.mark.parametrize("field,value", [("pan", "BADPAN"), ("phone", "12345"), ("dob", "2015-01-01"), ("monthly_income", 0), ("email", "not-an-email")])
def test_invalid_applicant_fields_are_rejected(client, applicant, field, value):
    body = payload()
    body["applicants"][0][field] = value
    assert client.post(f"{API}/applications", headers=applicant, json=body).status_code == 422


def test_pan_is_normalised_to_upper_case(client, applicant):
    body = payload()
    body["applicants"][0]["pan"] = "ashpr1234a"
    assert client.post(f"{API}/applications", headers=applicant, json=body).json()["applicants"][0]["pan"] == "ASHPR1234A"


def test_first_applicant_must_be_primary(client, applicant):
    body = payload()
    body["applicants"][0]["role"] = "CO_APPLICANT"
    assert client.post(f"{API}/applications", headers=applicant, json=body).status_code == 422


def test_draft_can_be_edited_and_consents_recorded(client, applicant):
    created = client.post(f"{API}/applications", headers=applicant, json=payload()).json()
    updated = client.patch(f"{API}/applications/{created['id']}", headers=applicant, json={"loan_amount": 4_000_000}).json()
    assert updated["loan_amount"] == 4_000_000
    consented = client.post(f"{API}/applications/{created['id']}/consents", headers=applicant, json={"scopes": {"kyc": True}}).json()
    assert consented["consents"] == {"kyc": True}
    assert client.post(f"{API}/applications/{created['id']}/consents", headers=applicant, json={"scopes": {"made_up": True}}).status_code == 422


def test_submitted_application_cannot_be_edited(client, run, applicant):
    approved = run("clean_home_loan")
    response = client.patch(f"{API}/applications/{approved['id']}", headers=applicant, json={"loan_amount": 1_000_000})
    assert response.status_code == 403


def test_register_search_filter_sort_and_paginate(client, run, auth):
    for key in ("clean_home_loan", "high_foir", "clean_lap", "weak_credit"):
        run(key)
    staff = auth["underwriter"]
    everything = client.get(f"{API}/applications", headers=staff, params={"page_size": 2}).json()
    assert everything["total"] == 4 and len(everything["items"]) == 2
    page_two = client.get(f"{API}/applications", headers=staff, params={"page_size": 2, "page": 2}).json()
    assert {i["id"] for i in everything["items"]}.isdisjoint({i["id"] for i in page_two["items"]})
    assert client.get(f"{API}/applications", headers=staff, params={"product": "LAP"}).json()["total"] == 1
    assert client.get(f"{API}/applications", headers=staff, params={"status": "REJECTED"}).json()["total"] == 2
    assert client.get(f"{API}/applications", headers=staff, params={"q": "priya"}).json()["items"][0]["applicant_name"] == "Priya Raman"
    amounts = [i["loan_amount"] for i in client.get(f"{API}/applications", headers=staff, params={"sort": "loan_amount", "order": "asc"}).json()["items"]]
    assert amounts == sorted(amounts)


def test_withdraw_closes_open_requests(client, run, applicant):
    pending = run("incomplete_application")
    assert pending["status"] == "ACTION_REQUIRED"
    withdrawn = client.post(f"{API}/applications/{pending['id']}/withdraw", headers=applicant).json()
    assert withdrawn["status"] == "WITHDRAWN"
    requests = client.get(f"{API}/applications/{pending['id']}/requests", headers=applicant).json()
    assert all(r["status"] == "WITHDRAWN" for r in requests)
    assert client.post(f"{API}/applications/{pending['id']}/withdraw", headers=applicant).status_code == 409
