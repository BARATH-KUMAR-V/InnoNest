import hashlib
import re
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import conflict, invalid
from app.models import Application, Document, ExtractedField, User
from app.models.mixins import utcnow
from app.services import audit, extraction
from app.services.catalog import DOC_LABELS

MAGIC = {"pdf": (b"%PDF",), "png": (b"\x89PNG",), "jpg": (b"\xff\xd8\xff",), "jpeg": (b"\xff\xd8\xff",)}
MIME = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}
USABLE_STATUSES = ("EXTRACTED", "NEEDS_REVIEW", "INTEGRITY_INDICATOR")


def validate_upload(filename: str, data: bytes, doc_type: str) -> str:
    problems = []
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if doc_type not in DOC_LABELS:
        problems.append({"field": "doc_type", "message": f"Unknown document type '{doc_type}'"})
    if extension not in settings.allowed_extensions:
        problems.append({"field": "file", "message": f"Only {', '.join(settings.allowed_extensions)} files are accepted"})
    elif not any(data.startswith(sig) for sig in MAGIC[extension]):
        problems.append({"field": "file", "message": "The file content does not match its extension"})
    if not data:
        problems.append({"field": "file", "message": "The file is empty"})
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        problems.append({"field": "file", "message": f"The file is larger than {settings.max_upload_mb} MB"})
    if problems:
        raise invalid("The upload was rejected", problems)
    return extension


def safe_name(filename: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", filename)[-80:]


def active_documents(db: Session, application_id: int) -> list[Document]:
    return list(db.execute(select(Document).where(Document.application_id == application_id, Document.status == "ACTIVE").order_by(Document.id)).scalars())


def attach_fields(document: Document, fields: list[dict]) -> None:
    document.fields.clear()
    for item in fields:
        document.fields.append(ExtractedField(name=item["name"], value=item["value"], numeric_value=item["numeric_value"], confidence=item["confidence"]))


def store_document(db: Session, application: Application, filename: str, data: bytes, doc_type: str, applicant_id: int | None, user: User) -> Document:
    extension = validate_upload(filename, data, doc_type)
    digest = hashlib.sha256(data).hexdigest()
    duplicate = db.execute(select(Document).where(Document.application_id == application.id, Document.sha256 == digest, Document.status == "ACTIVE")).first()
    if duplicate:
        raise conflict("This exact file has already been uploaded for this application")
    folder = Path(settings.upload_dir) / f"application_{application.id}"
    folder.mkdir(parents=True, exist_ok=True)
    stored = folder / f"{uuid.uuid4().hex[:10]}_{safe_name(filename)}"
    stored.write_bytes(data)
    result = extraction.analyse(data, extension)
    findings = list(result["findings"])
    detected = result["detected_type"]
    if detected and detected != doc_type and result["status"] != "UNREADABLE":
        findings.append({"id": "DOC-TYPE-MISMATCH", "severity": "MEDIUM", "text": f"The file was uploaded as {DOC_LABELS[doc_type]} but reads as {DOC_LABELS.get(detected, detected)}.", "evidence": [doc_type, detected]})
    document = Document(application_id=application.id, applicant_id=applicant_id, doc_type=doc_type, detected_type=detected, original_name=filename,
                        stored_path=str(stored), mime_type=MIME[extension], size_bytes=len(data), sha256=digest, status="ACTIVE",
                        extraction_status=result["status"], confidence=result["confidence"], text_excerpt=result["text_excerpt"], findings=findings,
                        metadata_info=result["metadata"], page_count=result["page_count"], ocr_used=result["ocr_used"], uploaded_by=user.id, uploaded_at=utcnow())
    attach_fields(document, result["fields"])
    db.add(document)
    db.flush()
    previous = db.execute(select(Document).where(Document.application_id == application.id, Document.doc_type == doc_type,
                                                  Document.applicant_id == applicant_id, Document.status == "ACTIVE", Document.id != document.id)).scalars()
    replaced = []
    for old in previous:
        old.status = "SUPERSEDED"
        old.superseded_by = document.id
        replaced.append(old.id)
    audit.record(db, "document.uploaded", application.id, user.email, user.role, "document", document.id,
                 {"doc_type": doc_type, "sha256": digest, "size_bytes": len(data), "extraction_status": result["status"], "replaced": replaced,
                  "finding_ids": [f["id"] for f in findings]})
    return document


def correct_field(db: Session, field: ExtractedField, new_value: str, user: User) -> ExtractedField:
    field.corrected_value = new_value.strip()
    field.corrected_by = user.id
    field.corrected_at = utcnow()
    audit.record(db, "document.field_corrected", field.document.application_id, user.email, user.role, "extracted_field", field.id,
                 {"field": field.name, "original": field.value, "corrected": field.corrected_value})
    return field


def field_map(documents: list[Document], doc_type: str, applicant_id: int | None = None) -> dict[str, ExtractedField]:
    for document in reversed(documents):
        if document.doc_type == doc_type and document.status == "ACTIVE" and document.extraction_status in USABLE_STATUSES:
            if applicant_id is None or document.applicant_id in (None, applicant_id):
                return {f.name: f for f in document.fields}
    return {}
