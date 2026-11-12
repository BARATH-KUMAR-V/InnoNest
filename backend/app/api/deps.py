from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import forbidden, not_found
from app.core.security import STAFF_ROLES, current_user, require_roles
from app.models import Application, Document, User

staff_only = require_roles(*STAFF_ROLES)
underwriter_only = require_roles("underwriter")
policy_admin_only = require_roles("policy_admin")
operator = require_roles("underwriter", "policy_admin")


def load_application(application_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Application:
    application = db.get(Application, application_id)
    if not application:
        raise not_found("Application")
    if user.role == "applicant" and application.owner_id != user.id:
        raise forbidden("This application belongs to another user")
    return application


def load_document(document_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Document:
    document = db.get(Document, document_id)
    if not document:
        raise not_found("Document")
    if user.role == "applicant" and document.application.owner_id != user.id:
        raise forbidden("This document belongs to another user")
    return document


def page_params(page: int = 1, page_size: int = 20) -> tuple[int, int]:
    return max(page, 1), min(max(page_size, 1), 100)
