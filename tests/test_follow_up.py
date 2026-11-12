import copy
from datetime import date

from app.demo.runner import upload
from app.demo.scenarios import SCENARIOS
from app.models import DocumentRequest, Notification
from app.core.database import SessionLocal
from app.services import docgen

API = "/api/v1"


def person_for(key):
    return SCENARIOS[key].application["applicants"][0]


def status_of(client, headers, app_id):
    return client.get(f"{API}/applications/{app_id}", headers=headers).json()["status"]


def test_missing_evidence_enters_action_required_not_rejection(client, run, applicant, underwriter):
    pending = run("incomplete_application")
    assert pending["status"] == "ACTION_REQUIRED"
    assert pending["pending_stage"] == "COMPLETENESS"
    assert pending["expires_at"]
    assert client.get(f"{API}/applications/{pending['id']}/decisions", headers=underwriter).json() == []


def test_checklist_lists_exactly_the_missing_items(client, run, applicant):
    pending = run("incomplete_application")
    checklist = client.get(f"{API}/applications/{pending['id']}/checklist", headers=applicant).json()
    open_items = [i for i in checklist["items"] if i["status"] == "OPEN"]
    assert sorted(i["doc_type"] for i in open_items) == ["BANK_STATEMENT", "SALARY_SLIP"]
    assert all(i["kind"] == "MISSING_DOCUMENT" for i in open_items)
    assert checklist["complete"] is False and checklist["open_count"] == 2


def test_requests_are_personalised_and_stored_in_the_database(client, run, applicant):
    pending = run("incomplete_application")
    requests = client.get(f"{API}/applications/{pending['id']}/requests", headers=applicant).json()
    assert len(requests) == 2 and all(r["status"] == "OPEN" for r in requests)
    assert all(r["message"].startswith("Lakshmi") for r in requests)
    db = SessionLocal()
    try:
        assert db.query(DocumentRequest).filter_by(application_id=pending["id"]).count() == 2
    finally:
        db.close()


def test_notifications_are_created_on_every_channel_and_labelled_simulated(client, run, applicant):
    pending = run("incomplete_application")
    notes = client.get(f"{API}/notifications", headers=applicant, params={"application_id": pending["id"]}).json()
    by_channel = {n["channel"]: n for n in notes["items"] if n["kind"] == "ACTION_REQUIRED"}
    assert set(by_channel) == {"IN_APP", "EMAIL", "SMS"}
    assert by_channel["EMAIL"]["simulated"] and by_channel["SMS"]["simulated"]
    assert by_channel["EMAIL"]["delivery_status"] == "SIMULATED_NOT_SENT"
    assert not by_channel["IN_APP"]["simulated"]
    assert "salary slip" in by_channel["IN_APP"]["body"].lower()
    assert "InnoNest" in by_channel["IN_APP"]["subject"]


def test_partial_upload_keeps_waiting_and_tells_the_applicant(client, run, applicant, docs_for):
    pending = run("incomplete_application")
    ids = [a["id"] for a in pending["applicants"]]
    upload(client, applicant, pending["id"], ids, docs_for("incomplete_application", ["SALARY_SLIP"])[0])
    assert status_of(client, applicant, pending["id"]) == "ACTION_REQUIRED"
    requests = client.get(f"{API}/applications/{pending['id']}/requests", headers=applicant).json()
    assert sorted(r["status"] for r in requests) == ["FULFILLED", "OPEN"]
    kinds = [n["kind"] for n in client.get(f"{API}/notifications", headers=applicant, params={"application_id": pending["id"]}).json()["items"]]
    assert "PROGRESS" in kinds


def test_workflow_resumes_automatically_after_the_last_upload(client, run, applicant, underwriter, docs_for):
    pending = run("incomplete_application")
    ids = [a["id"] for a in pending["applicants"]]
    for doc_type in ("SALARY_SLIP", "BANK_STATEMENT"):
        upload(client, applicant, pending["id"], ids, docs_for("incomplete_application", [doc_type])[0])
    final = client.get(f"{API}/applications/{pending['id']}", headers=applicant).json()
    assert final["status"] == "APPROVED"
    assert final["pending_stage"] is None
    history = client.get(f"{API}/applications/{pending['id']}/history", headers=applicant).json()
    transitions = [e["details"]["to"] for e in history if e["action"] == "application.status_changed"]
    assert transitions[:2] == ["SUBMITTED", "PROCESSING"]
    assert "ACTION_REQUIRED" in transitions and "DOCUMENTS_RECEIVED" in transitions and transitions[-1] == "APPROVED"
    decision = client.get(f"{API}/applications/{pending['id']}/decisions", headers=underwriter).json()[0]
    assert decision["outcome"] == "APPROVE"
    requests = client.get(f"{API}/applications/{pending['id']}/requests", headers=applicant).json()
    assert all(r["status"] == "FULFILLED" for r in requests)


def test_replaced_document_is_revalidated(client, run, applicant, docs_for):
    pending = run("incomplete_application")
    ids = [a["id"] for a in pending["applicants"]]
    wrong = docs_for("incomplete_application", ["FORM16"])[0] | {"doc_type": "SALARY_SLIP"}
    response = upload(client, applicant, pending["id"], ids, wrong)
    assert "DOC-TYPE-MISMATCH" in [f["id"] for f in response["findings"]]
    checklist = client.get(f"{API}/applications/{pending['id']}/checklist", headers=applicant).json()
    slip = next(i for i in checklist["items"] if i["doc_type"] == "SALARY_SLIP")
    assert slip["kind"] == "WRONG_DOCUMENT"
    upload(client, applicant, pending["id"], ids, docs_for("incomplete_application", ["SALARY_SLIP"])[0])
    checklist = client.get(f"{API}/applications/{pending['id']}/checklist", headers=applicant).json()
    assert next(i for i in checklist["items"] if i["doc_type"] == "SALARY_SLIP")["status"] == "SATISFIED"
    documents = client.get(f"{API}/applications/{pending['id']}/documents", headers=applicant, params={"include_replaced": "true"}).json()
    assert sorted(d["status"] for d in documents if d["doc_type"] == "SALARY_SLIP") == ["ACTIVE", "SUPERSEDED"]


def test_missing_fields_are_requested_and_resume_after_update(client, run, applicant):
    body = copy.deepcopy(SCENARIOS["clean_home_loan"].application)
    body["property_address"] = ""
    body["applicants"][0]["address"] = ""
    created = client.post(f"{API}/applications", headers=applicant, json=body).json()
    client.post(f"{API}/applications/{created['id']}/consents", headers=applicant, json={"scopes": {"data_processing": True, "kyc": True, "credit_bureau": True, "bank_statement": True}})
    ids = [a["id"] for a in created["applicants"]]
    from app.demo.scenarios import generate_documents
    for item in generate_documents(SCENARIOS["clean_home_loan"]):
        upload(client, applicant, created["id"], ids, item)
    submitted = client.post(f"{API}/applications/{created['id']}/submit", headers=applicant).json()
    assert submitted["status"] == "ACTION_REQUIRED"
    kinds = {r["kind"] for r in client.get(f"{API}/applications/{created['id']}/requests", headers=applicant).json() if r["status"] == "OPEN"}
    assert kinds == {"MISSING_FIELD"}
    person = {**body["applicants"][0], "id": ids[0], "address": "14 Lakeview Road, Adyar"}
    client.patch(f"{API}/applications/{created['id']}", headers=applicant, json={"property_address": "Flat 4B, Palm Grove Apartments, Velachery", "applicants": [person]})
    assert status_of(client, applicant, created["id"]) == "APPROVED"


def test_missing_consent_blocks_processing_until_given(client, run, applicant):
    created = client.post(f"{API}/applications", headers=applicant, json=copy.deepcopy(SCENARIOS["clean_home_loan"].application)).json()
    ids = [a["id"] for a in created["applicants"]]
    from app.demo.scenarios import generate_documents
    for item in generate_documents(SCENARIOS["clean_home_loan"]):
        upload(client, applicant, created["id"], ids, item)
    submitted = client.post(f"{API}/applications/{created['id']}/submit", headers=applicant).json()
    assert submitted["status"] == "ACTION_REQUIRED"
    requests = client.get(f"{API}/applications/{created['id']}/requests", headers=applicant).json()
    assert {r["kind"] for r in requests} == {"CONSENT"} and len(requests) == 4
    client.post(f"{API}/applications/{created['id']}/consents", headers=applicant, json={"scopes": {"data_processing": True, "kyc": True, "credit_bureau": True, "bank_statement": True}})
    assert status_of(client, applicant, created["id"]) == "APPROVED"


def test_conflicting_name_is_requested_and_explained_goes_to_review(client, run, applicant, underwriter, docs_for):
    pending = run("incomplete_application")
    ids = [a["id"] for a in pending["applicants"]]
    application = SCENARIOS["incomplete_application"].application
    other_name = {**person_for("incomplete_application"), "full_name": "Lakshmi Narayanan", "dob": date(1991, 12, 2)}
    flat = application | {"property_area_sqft": application["property_area_sqft"]}
    pan_doc = {"doc_type": "PAN", "filename": "pan_other_name.pdf", "content": docgen.make_document("PAN", flat, other_name), "applicant_index": 0}
    upload(client, applicant, pending["id"], ids, pan_doc)
    checklist = client.get(f"{API}/applications/{pending['id']}/checklist", headers=applicant).json()
    conflict = next(i for i in checklist["items"] if i["kind"] == "CONFLICT")
    assert conflict["status"] == "OPEN" and "does not match" in conflict["message"]
    request = next(r for r in client.get(f"{API}/applications/{pending['id']}/requests", headers=applicant).json() if r["kind"] == "CONFLICT" and r["status"] == "OPEN")
    for doc_type in ("SALARY_SLIP", "BANK_STATEMENT"):
        upload(client, applicant, pending["id"], ids, docs_for("incomplete_application", [doc_type])[0])
    assert status_of(client, applicant, pending["id"]) == "ACTION_REQUIRED"
    explained = client.post(f"{API}/applications/{pending['id']}/clarifications", headers=applicant, json={"request_id": request["id"], "response": "My name on the PAN card was recorded after marriage."})
    assert explained.status_code == 200
    assert status_of(client, applicant, pending["id"]) == "REFERRED"
    codes = [r["code"] for r in client.get(f"{API}/applications/{pending['id']}/decisions", headers=underwriter).json()[0]["reason_codes"]]
    assert "EXPLAINED_CONFLICTS" in codes


def test_clarification_only_for_conflicts(client, run, applicant):
    pending = run("incomplete_application")
    request = client.get(f"{API}/applications/{pending['id']}/requests", headers=applicant).json()[0]
    response = client.post(f"{API}/applications/{pending['id']}/clarifications", headers=applicant, json={"request_id": request["id"], "response": "Please skip this document"})
    assert response.status_code == 422


def test_reminders_follow_configured_intervals(client, run, applicant, auth):
    config = client.put(f"{API}/follow-up/config", headers=auth["policy_admin"], json={"reminder_intervals_hours": [1, 2], "expiry_days": 10})
    assert config.status_code == 200
    pending = run("incomplete_application")
    assert client.post(f"{API}/follow-up/run", headers=auth["underwriter"], json={"advance_hours": 0}).json()["actions"] == []
    first = client.post(f"{API}/follow-up/run", headers=auth["underwriter"], json={"advance_hours": 2}).json()["actions"]
    assert first == [{"application": pending["reference"], "action": "REMINDER", "number": 1}]
    again = client.post(f"{API}/follow-up/run", headers=auth["underwriter"], json={"advance_hours": 2}).json()["actions"]
    assert again == []
    second = client.post(f"{API}/follow-up/run", headers=auth["underwriter"], json={"advance_hours": 6}).json()["actions"]
    assert second[0]["number"] == 2
    exhausted = client.post(f"{API}/follow-up/run", headers=auth["underwriter"], json={"advance_hours": 24 * 5}).json()["actions"]
    assert exhausted == []
    reminders = [n for n in client.get(f"{API}/notifications", headers=applicant, params={"channel": "IN_APP"}).json()["items"] if n["kind"] == "REMINDER"]
    assert len(reminders) == 2
    requests = client.get(f"{API}/applications/{pending['id']}/requests", headers=applicant).json()
    assert all(r["reminders_sent"] == 2 for r in requests)


def test_application_expires_when_nothing_arrives(client, run, applicant, auth):
    client.put(f"{API}/follow-up/config", headers=auth["policy_admin"], json={"reminder_intervals_hours": [24], "expiry_days": 3})
    pending = run("incomplete_application")
    actions = client.post(f"{API}/follow-up/run", headers=auth["underwriter"], json={"advance_hours": 24 * 4}).json()["actions"]
    assert actions == [{"application": pending["reference"], "action": "EXPIRED"}]
    assert status_of(client, applicant, pending["id"]) == "EXPIRED"
    kinds = [n["kind"] for n in client.get(f"{API}/notifications", headers=applicant).json()["items"]]
    assert "EXPIRED" in kinds


def test_follow_up_config_is_validated(client, auth):
    assert client.put(f"{API}/follow-up/config", headers=auth["policy_admin"], json={"reminder_intervals_hours": [0], "expiry_days": 5}).status_code == 422
    assert client.put(f"{API}/follow-up/config", headers=auth["policy_admin"], json={"reminder_intervals_hours": [], "expiry_days": 5}).status_code == 422
    assert client.put(f"{API}/follow-up/config", headers=auth["applicant"], json={"reminder_intervals_hours": [5], "expiry_days": 5}).status_code == 403


def test_notifications_can_be_marked_read(client, run, applicant):
    run("incomplete_application")
    notes = client.get(f"{API}/notifications", headers=applicant).json()
    assert notes["unread_in_app"] >= 1
    first = next(n for n in notes["items"] if n["channel"] == "IN_APP")
    assert client.post(f"{API}/notifications/{first['id']}/read", headers=applicant).json()["read_at"]
    assert client.post(f"{API}/notifications/read-all", headers=applicant).status_code == 200
    assert client.get(f"{API}/notifications", headers=applicant).json()["unread_in_app"] == 0
