import csv
import io

from app.core.database import SessionLocal
from app.models import AuditEvent
from app.services import audit

API = "/api/v1"


def actions(client, headers, app_id):
    return [e["action"] for e in client.get(f"{API}/audit", headers=headers, params={"application_id": app_id, "page_size": 100}).json()["items"]][::-1]


def test_audit_trail_covers_the_full_lifecycle(client, run, auth):
    pending = run("incomplete_application")
    from app.demo.runner import upload
    from app.demo.scenarios import generate_documents, SCENARIOS
    ids = [a["id"] for a in pending["applicants"]]
    for item in generate_documents(SCENARIOS["incomplete_application"], ["SALARY_SLIP", "BANK_STATEMENT"]):
        upload(client, auth["applicant"], pending["id"], ids, item)
    trail = actions(client, auth["auditor"], pending["id"])
    for expected in ("application.created", "application.consent", "document.uploaded", "application.submitted", "followup.request_created", "notification.created",
                     "followup.request_fulfilled", "provider.calls_completed", "verification.completed", "decision.recorded", "application.status_changed"):
        assert expected in trail, expected
    assert trail.index("application.submitted") < trail.index("followup.request_created") < trail.index("decision.recorded")


def test_reminders_and_clarifications_are_audited(client, run, auth):
    pending = run("incomplete_application")
    client.put(f"{API}/follow-up/config", headers=auth["policy_admin"], json={"reminder_intervals_hours": [1], "expiry_days": 10})
    client.post(f"{API}/follow-up/run", headers=auth["underwriter"], json={"advance_hours": 3})
    assert "followup.reminder_sent" in actions(client, auth["auditor"], pending["id"])


def test_audit_entries_record_actor_role_and_details(client, run, auth):
    run("clean_home_loan")
    uploads = client.get(f"{API}/audit", headers=auth["auditor"], params={"action": "document.uploaded", "page_size": 100}).json()["items"]
    assert uploads and all(e["actor"] == "applicant@example.com" and e["actor_role"] == "applicant" and e["details"]["sha256"] for e in uploads)
    decision = client.get(f"{API}/audit", headers=auth["auditor"], params={"action": "decision.recorded"}).json()["items"][0]
    assert decision["actor"] == "decision-engine" and decision["details"]["policy_version"] == 1


def test_hash_chain_detects_tampering(client, run, auth):
    run("clean_home_loan")
    assert client.get(f"{API}/audit/verify", headers=auth["auditor"]).json()["intact"] is True
    db = SessionLocal()
    try:
        victim = db.query(AuditEvent).filter(AuditEvent.action == "application.submitted").one()
        victim.details = {"product": "LAP"}
        db.commit()
        broken = audit.verify_chain(db)
    finally:
        db.close()
    assert broken["intact"] is False and broken["broken_at"] == victim.id


def test_audit_filters_and_pagination(client, run, auth):
    run("clean_home_loan")
    page = client.get(f"{API}/audit", headers=auth["auditor"], params={"page_size": 5}).json()
    assert len(page["items"]) == 5 and page["total"] > 5
    only = client.get(f"{API}/audit", headers=auth["auditor"], params={"action": "decision"}).json()
    assert only["total"] >= 1 and all(e["action"].startswith("decision") for e in only["items"])
    assert client.get(f"{API}/audit", headers=auth["auditor"], params={"actor": "nobody@nowhere"}).json()["total"] == 0


def test_dashboard_is_computed_from_the_database(client, run, auth):
    empty = client.get(f"{API}/reports/dashboard", headers=auth["underwriter"]).json()
    assert empty["total"] == 0 and empty["approved"] == 0
    for key in ("clean_home_loan", "clean_lap", "high_foir", "aml_potential_match", "incomplete_application"):
        run(key)
    stats = client.get(f"{API}/reports/dashboard", headers=auth["underwriter"]).json()
    assert (stats["total"], stats["approved"], stats["rejected"], stats["referred"], stats["action_required"]) == (5, 2, 1, 1, 1)
    products = {p["product"]: p["count"] for p in stats["product_distribution"]}
    assert products == {"HOME_LOAN": 4, "LAP": 1}
    assert sum(s["count"] for s in stats["status_breakdown"]) == 5
    assert stats["approval_rate"] == round(2 / 3, 4)
    assert stats["recent_activity"] and stats["recent_activity"][0]["reference"].startswith("INN-")
    by_product = {p["product"]: p for p in stats["outcomes_by_product"]}
    assert by_product["LAP"]["APPROVED"] == 1 and by_product["HOME_LOAN"]["REJECTED"] == 1


def test_csv_exports(client, run, auth):
    for key in ("clean_home_loan", "high_foir"):
        run(key)
    response = client.get(f"{API}/reports/applications.csv", headers=auth["underwriter"], params={"status": "APPROVED"})
    assert response.headers["content-type"].startswith("text/csv") and "innonest-applications.csv" in response.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0][:3] == ["reference", "product", "status"] and len(rows) == 2 and rows[1][2] == "APPROVED"
    decisions = list(csv.DictReader(io.StringIO(client.get(f"{API}/reports/decisions.csv", headers=auth["underwriter"]).text)))
    assert {d["outcome"] for d in decisions} == {"APPROVE", "REJECT"} and all(len(d["result_hash"]) == 64 for d in decisions)
    audit_rows = list(csv.reader(io.StringIO(client.get(f"{API}/reports/audit.csv", headers=auth["auditor"]).text)))
    assert audit_rows[0][0] == "id" and len(audit_rows) > 10
    assert client.get(f"{API}/reports/audit.csv", headers=auth["applicant"]).status_code == 403
    assert client.get(f"{API}/reports/applications.csv", headers=auth["applicant"]).status_code == 403


def test_health_endpoint_identifies_the_service(client):
    body = client.get("/api/health").json()
    assert body == {"status": "ok", "service": "InnoNest"}
    assert client.get("/openapi.json").json()["info"]["title"] == "InnoNest API"
