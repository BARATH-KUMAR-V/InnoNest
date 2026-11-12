from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User
from app.services import policies

DEMO_USERS = [
    ("applicant@example.com", "Applicant@123", "Demo Applicant", "applicant", "9876500001"),
    ("applicant2@example.com", "Applicant@123", "Second Applicant", "applicant", "9876500002"),
    ("underwriter@example.com", "Underwriter@123", "Uma Underwriter", "underwriter", None),
    ("policy@example.com", "PolicyAdmin@123", "Pranav Policy", "policy_admin", None),
    ("auditor@example.com", "Auditor@123", "Anand Auditor", "auditor", None),
]


def seed_reference_data(db: Session) -> None:
    policies.seed_policies(db)
    db.commit()


def seed_users(db: Session) -> None:
    for email, password, name, role, phone in DEMO_USERS:
        if db.execute(select(User).where(User.email == email)).first():
            continue
        db.add(User(email=email, password_hash=hash_password(password), full_name=name, role=role, phone=phone))
    db.commit()
