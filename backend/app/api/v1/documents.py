from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import load_application, load_document
from app.core.database import get_db
from app.core.errors import conflict, forbidden, invalid, not_found
from app.core.security import current_user
from app.models import Application, Document, ExtractedField, User
from app.schemas.common import DocumentOut, FieldCorrection, FieldOut
from app.services import documents as docs, workflow
from app.services.catalog import DOC_LABELS

router = APIRouter(tags=["documents"])
UPLOAD_STATUSES = ("DRAFT", "ACTION_REQUIRED", "VERIFICATION_PENDING", "REFERRED")


@router.get("/document-types")
def document_types():
    return [{"doc_type": key, "label": label} for key, label in DOC_LABELS.items()]


@router.post("/applications/{application_id}/documents", response_model=DocumentOut, status_code=201)
async def upload_document(doc_type: str = Form(...), applicant_id: int | None = Form(default=None), file: UploadFile = File(...),
                          application: Application = Depends(load_application), db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role not in ("applicant", "underwriter"):
        raise forbidden("This role cannot upload documents")
    if application.status not in UPLOAD_STATUSES:
        raise conflict(f"Documents cannot be added while the application is {application.status.replace('_', ' ').lower()}")
    if applicant_id is not None and applicant_id not in {a.id for a in application.applicants}:
        raise invalid("The applicant does not belong to this application", [{"field": "applicant_id", "message": "Unknown applicant"}])
    data = await file.read()
    document = docs.store_document(db, application, file.filename or "upload", data, doc_type, applicant_id, user)
    db.flush()
    workflow.revalidate(db, application, user, f"document uploaded: {DOC_LABELS[doc_type]}")
    db.commit()
    return document


@router.get("/applications/{application_id}/documents", response_model=list[DocumentOut])
def list_documents(include_replaced: bool = False, application: Application = Depends(load_application)):
    return [d for d in application.documents if include_replaced or d.status == "ACTIVE"]


@router.get("/documents/{document_id}")
def get_document(document: Document = Depends(load_document)):
    return {"document": DocumentOut.model_validate(document), "fields": [FieldOut.model_validate(f) for f in document.fields], "text_excerpt": document.text_excerpt,
            "notice": "Extraction and hashing describe the file. They do not prove that a document is authentic."}


@router.get("/documents/{document_id}/file")
def download_document(document: Document = Depends(load_document)):
    path = Path(document.stored_path)
    if not path.exists():
        raise not_found("The stored file")
    return FileResponse(path, media_type=document.mime_type, filename=document.original_name)


@router.patch("/document-fields/{field_id}", response_model=FieldOut)
def correct_field(payload: FieldCorrection, field_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    field = db.get(ExtractedField, field_id)
    if not field:
        raise not_found("Field")
    application = field.document.application
    if user.role == "applicant" and application.owner_id != user.id:
        raise forbidden("This field belongs to another user")
    if user.role not in ("applicant", "underwriter"):
        raise forbidden("This role cannot correct extracted values")
    if application.status in ("APPROVED", "REJECTED", "EXPIRED", "WITHDRAWN"):
        raise conflict("This application is closed")
    docs.correct_field(db, field, payload.value, user)
    db.flush()
    workflow.revalidate(db, application, user, "extracted value corrected")
    db.commit()
    return field
