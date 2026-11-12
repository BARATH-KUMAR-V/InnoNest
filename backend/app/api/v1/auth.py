from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError, conflict
from app.core.security import create_token, current_user, hash_password, verify_password
from app.models import User
from app.schemas.common import LoginIn, RegisterIn, TokenOut, UserOut
from app.services import audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == payload.email.lower())).scalar_one_or_none()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        audit.record(db, "auth.login_failed", actor=payload.email.lower(), actor_role="unknown")
        db.commit()
        raise AppError(401, "invalid_credentials", "The email or password is not correct")
    audit.record(db, "auth.login", actor=user.email, actor_role=user.role)
    db.commit()
    return TokenOut(access_token=create_token(user), user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenOut, status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.execute(select(User).where(User.email == email)).first():
        raise conflict("An account with this email already exists")
    user = User(email=email, password_hash=hash_password(payload.password), full_name=payload.full_name.strip(), role="applicant", phone=payload.phone)
    db.add(user)
    db.flush()
    audit.record(db, "auth.registered", actor=user.email, actor_role="applicant", entity="user", entity_id=user.id)
    db.commit()
    return TokenOut(access_token=create_token(user), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user
