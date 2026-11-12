import copy

from app.demo.scenarios import SCENARIOS

API = "/api/v1"


def test_login_returns_token_and_role(client):
    response = client.post(f"{API}/auth/login", json={"email": "underwriter@example.com", "password": "Underwriter@123"})
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["role"] == "underwriter"
    assert body["access_token"]


def test_wrong_password_is_rejected_and_audited(client, auth):
    response = client.post(f"{API}/auth/login", json={"email": "underwriter@example.com", "password": "nope"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"
    events = client.get(f"{API}/audit", headers=auth["auditor"], params={"action": "auth.login_failed"}).json()
    assert events["total"] == 1


def test_register_creates_applicant_account(client):
    response = client.post(f"{API}/auth/register", json={"email": "new.person@example.com", "password": "LongEnough1", "full_name": "New Person"})
    assert response.status_code == 201
    assert response.json()["user"]["role"] == "applicant"
    duplicate = client.post(f"{API}/auth/register", json={"email": "new.person@example.com", "password": "LongEnough1", "full_name": "New Person"})
    assert duplicate.status_code == 409


def test_protected_routes_need_a_token(client):
    response = client.get(f"{API}/applications")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_garbage_token_is_rejected(client):
    response = client.get(f"{API}/applications", headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 401


def test_applicant_cannot_see_another_applicants_application(client, run, auth):
    created = run("clean_home_loan", submit=False)
    other = auth["other_applicant"]
    assert client.get(f"{API}/applications/{created['id']}", headers=other).status_code == 403
    assert client.get(f"{API}/applications", headers=other).json()["total"] == 0


def test_applicant_cannot_use_staff_endpoints(client, run, applicant):
    created = run("clean_home_loan")
    for url in (f"{API}/reports/dashboard", f"{API}/audit", f"{API}/integrations", f"{API}/applications/{created['id']}/verification", f"{API}/applications/{created['id']}/evidence-graph"):
        assert client.get(url, headers=applicant).status_code == 403, url


def test_staff_cannot_create_applications(client, underwriter):
    response = client.post(f"{API}/applications", headers=underwriter, json=copy.deepcopy(SCENARIOS["clean_home_loan"].application))
    assert response.status_code == 403


def test_only_policy_admin_can_publish_policy_versions(client, auth):
    body = {"params": {"min_age": 22}, "change_note": "Raise the minimum age"}
    assert client.put(f"{API}/policies/balanced", headers=auth["underwriter"], json=body).status_code == 403
    assert client.put(f"{API}/policies/balanced", headers=auth["auditor"], json=body).status_code == 403
    assert client.put(f"{API}/policies/balanced", headers=auth["policy_admin"], json=body).status_code == 200


def test_only_underwriter_can_review_referrals(client, run, auth):
    referred = run("aml_potential_match")
    body = {"outcome": "APPROVE", "note": "Reviewed the screening evidence"}
    assert client.post(f"{API}/applications/{referred['id']}/review", headers=auth["auditor"], json=body).status_code == 403
    assert client.post(f"{API}/applications/{referred['id']}/review", headers=auth["policy_admin"], json=body).status_code == 403
    assert client.post(f"{API}/applications/{referred['id']}/review", headers=auth["applicant"], json=body).status_code == 403


def test_applicant_decision_view_hides_internal_inputs(client, run, applicant):
    approved = run("clean_home_loan")
    decisions = client.get(f"{API}/applications/{approved['id']}/decisions", headers=applicant).json()
    assert decisions[0]["outcome"] == "APPROVE"
    assert decisions[0]["inputs"] == {} and decisions[0]["outputs"] == {}


def test_errors_use_one_envelope(client, applicant):
    response = client.get(f"{API}/applications/99999", headers=applicant)
    assert response.status_code == 404
    assert set(response.json()["error"]) == {"code", "message", "details"}
