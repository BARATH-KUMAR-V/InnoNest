import hashlib
from datetime import date

import pytest

from app.models import Application
from app.services import docgen

API = "/api/v1"

SAMPLE_APPLICATION = {"survey_no": "142/3A", "property_city": "Chennai", "property_address": "Flat 4B", "property_area_sqft": 1150, "declared_value": 6000000, "owner_name": "Seller", "seller_name": "Seller"}
SAMPLE_PERSON = {"full_name": "Priya Raman", "pan": "ASHPR1234A", "dob": date(1990, 3, 14), "monthly_income": 95000, "employment_type": "SALARIED", "employer": "Meridian Software Pvt Ltd", "address": "14 Lakeview Road", "city": "Chennai"}


def draft(run):
    return run("clean_home_loan", submit=False)


def upload(client, headers, application, doc_type, name, content, mime="application/pdf"):
    return client.post(f"{API}/applications/{application['id']}/documents", headers=headers, data={"doc_type": doc_type, "applicant_id": str(application["applicants"][0]["id"])},
                       files={"file": (name, content, mime)})


def test_upload_stores_hash_links_application_and_extracts_fields(client, run, applicant):
    app_ = run("clean_home_loan", submit=False)
    documents = client.get(f"{API}/applications/{app_['id']}/documents", headers=applicant).json()
    assert documents
    slip = next(d for d in documents if d["doc_type"] == "SALARY_SLIP")
    assert slip["application_id"] == app_["id"]
    assert len(slip["sha256"]) == 64
    assert slip["extraction_status"] == "EXTRACTED"
    detail = client.get(f"{API}/documents/{slip['id']}", headers=applicant).json()
    fields = {f["name"]: f for f in detail["fields"]}
    assert fields["net_pay"]["numeric_value"] == 95000.0
    assert fields["net_pay"]["confidence"] > 0.9
    assert "do not prove" in detail["notice"]
    stored = client.get(f"{API}/documents/{slip['id']}/file", headers=applicant)
    assert hashlib.sha256(stored.content).hexdigest() == slip["sha256"]


def test_upload_rejects_wrong_extension(client, run, applicant):
    app_ = draft(run)
    response = upload(client, applicant, app_, "PAN", "card.exe", b"MZ....", "application/octet-stream")
    assert response.status_code == 422
    assert any(d["field"] == "file" for d in response.json()["error"]["details"])


def test_upload_rejects_content_that_does_not_match_extension(client, run, applicant):
    app_ = draft(run)
    assert upload(client, applicant, app_, "PAN", "card.pdf", b"this is plain text, not a pdf").status_code == 422


def test_upload_rejects_empty_and_oversized_files(client, run, applicant):
    app_ = draft(run)
    assert upload(client, applicant, app_, "PAN", "empty.pdf", b"").status_code == 422
    assert upload(client, applicant, app_, "PAN", "huge.pdf", b"%PDF" + b"0" * (9 * 1024 * 1024)).status_code == 422


def test_upload_rejects_unknown_document_type(client, run, applicant):
    app_ = draft(run)
    content = docgen.make_document("PAN", SAMPLE_APPLICATION | {"property_area_sqft": 1}, SAMPLE_PERSON)
    assert upload(client, applicant, app_, "PASSPORT_PHOTO", "x.pdf", content).status_code == 422


def test_identical_file_cannot_be_uploaded_twice(client, run, applicant):
    app_ = draft(run)
    documents = client.get(f"{API}/applications/{app_['id']}/documents", headers=applicant).json()
    existing = next(d for d in documents if d["doc_type"] == "PAN")
    content = client.get(f"{API}/documents/{existing['id']}/file", headers=applicant).content
    assert upload(client, applicant, app_, "PAN", "pan.pdf", content).status_code == 409


def test_replacing_a_document_supersedes_the_old_one(client, run, applicant):
    app_ = draft(run)
    replacement = docgen.make_document("PAN", SAMPLE_APPLICATION, {**SAMPLE_PERSON, "dob": date(1990, 3, 14)}, edited=False) + b"\n%replacement"
    response = upload(client, applicant, app_, "PAN", "pan_new.pdf", replacement)
    assert response.status_code == 201
    everything = client.get(f"{API}/applications/{app_['id']}/documents", headers=applicant, params={"include_replaced": "true"}).json()
    pans = [d for d in everything if d["doc_type"] == "PAN"]
    assert sorted(d["status"] for d in pans) == ["ACTIVE", "SUPERSEDED"]
    active = client.get(f"{API}/applications/{app_['id']}/documents", headers=applicant).json()
    assert len([d for d in active if d["doc_type"] == "PAN"]) == 1


def test_scanned_image_is_read_with_ocr(client, run, applicant):
    app_ = draft(run)
    scan = docgen.to_scan(docgen.make_document("PAN", SAMPLE_APPLICATION, SAMPLE_PERSON))
    response = upload(client, applicant, app_, "PAN", "pan_scan.png", scan, "image/png")
    assert response.status_code == 201
    body = response.json()
    assert body["ocr_used"] is True
    assert body["detected_type"] == "PAN"
    assert 0.5 < body["confidence"] <= 1
    detail = client.get(f"{API}/documents/{body['id']}", headers=applicant).json()
    assert any(f["name"] == "pan" and f["value"] == "ASHPR1234A" for f in detail["fields"])


def test_unreadable_image_is_flagged_and_asked_again(client, run, applicant):
    import cv2
    import numpy as np
    app_ = run("incomplete_application")
    blank = cv2.imencode(".png", np.full((400, 600, 3), 255, dtype=np.uint8))[1].tobytes()
    response = client.post(f"{API}/applications/{app_['id']}/documents", headers=applicant, data={"doc_type": "SALARY_SLIP", "applicant_id": str(app_["applicants"][0]["id"])},
                           files={"file": ("slip.png", blank, "image/png")})
    assert response.status_code == 201
    assert response.json()["extraction_status"] == "UNREADABLE"
    checklist = client.get(f"{API}/applications/{app_['id']}/checklist", headers=applicant).json()
    item = next(i for i in checklist["items"] if i["doc_type"] == "SALARY_SLIP")
    assert item["kind"] == "UNREADABLE_DOCUMENT" and item["status"] == "OPEN"


def test_edited_salary_slip_raises_indicators_not_a_fraud_finding(client, run, auth):
    tampered = run("tampered_slip", submit=False)
    documents = client.get(f"{API}/applications/{tampered['id']}/documents", headers=auth["applicant"]).json()
    slip = next(d for d in documents if d["doc_type"] == "SALARY_SLIP")
    ids = {f["id"] for f in slip["findings"]}
    assert {"DOC-META-PRODUCER", "DOC-META-MODIFIED", "DOC-FONT-MISMATCH"} <= ids
    assert slip["extraction_status"] == "INTEGRITY_INDICATOR"
    assert not any("fraud" in f["text"].lower() and "confirmed" in f["text"].lower() for f in slip["findings"])


def test_field_correction_keeps_original_and_is_audited(client, run, applicant, auth):
    app_ = draft(run)
    documents = client.get(f"{API}/applications/{app_['id']}/documents", headers=applicant).json()
    slip = next(d for d in documents if d["doc_type"] == "SALARY_SLIP")
    detail = client.get(f"{API}/documents/{slip['id']}", headers=applicant).json()
    field = next(f for f in detail["fields"] if f["name"] == "employer")
    response = client.patch(f"{API}/document-fields/{field['id']}", headers=applicant, json={"value": "Corrected Employer Ltd"})
    assert response.status_code == 200
    assert response.json()["corrected_value"] == "Corrected Employer Ltd"
    assert response.json()["value"] == field["value"]
    events = client.get(f"{API}/audit", headers=auth["auditor"], params={"action": "document.field_corrected"}).json()
    assert events["total"] == 1 and events["items"][0]["details"]["original"] == field["value"]


def test_other_applicant_cannot_download_document(client, run, auth):
    app_ = draft(run)
    documents = client.get(f"{API}/applications/{app_['id']}/documents", headers=auth["applicant"]).json()
    assert client.get(f"{API}/documents/{documents[0]['id']}/file", headers=auth["other_applicant"]).status_code == 403


def test_documents_cannot_be_added_to_a_decided_application(client, run, applicant):
    approved = run("clean_home_loan")
    content = docgen.make_document("PAN", SAMPLE_APPLICATION, SAMPLE_PERSON) + b"\n%x"
    response = upload(client, applicant, approved, "PAN", "late.pdf", content)
    assert response.status_code == 409
