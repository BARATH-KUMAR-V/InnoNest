from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import Timestamps


class Application(Base, Timestamps):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True, default="DRAFT")
    pending_stage: Mapped[str | None] = mapped_column(String(30), nullable=True)
    loan_amount: Mapped[float] = mapped_column(Float)
    interest_rate: Mapped[float] = mapped_column(Float)
    tenure_months: Mapped[int] = mapped_column(Integer)
    purpose: Mapped[str] = mapped_column(String(60))
    end_use: Mapped[str | None] = mapped_column(String(60), nullable=True)
    policy_key: Mapped[str] = mapped_column(String(30), default="balanced")
    property_type: Mapped[str] = mapped_column(String(40))
    property_subtype: Mapped[str] = mapped_column(String(30), default="RESIDENTIAL")
    property_city: Mapped[str] = mapped_column(String(80))
    property_address: Mapped[str] = mapped_column(String(300), default="")
    property_pincode: Mapped[str] = mapped_column(String(10), default="")
    property_area_sqft: Mapped[float] = mapped_column(Float, default=0)
    locality_tier: Mapped[int] = mapped_column(Integer, default=2)
    survey_no: Mapped[str] = mapped_column(String(60), default="")
    declared_value: Mapped[float] = mapped_column(Float)
    seller_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    owner_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    existing_mortgage_amount: Mapped[float] = mapped_column(Float, default=0)
    under_construction: Mapped[bool] = mapped_column(Boolean, default=False)
    consents: Mapped[dict] = mapped_column(JSON, default=dict)
    resolved_conflicts: Mapped[list] = mapped_column(JSON, default=list)
    stage_state: Mapped[dict] = mapped_column(JSON, default=dict)
    language: Mapped[str] = mapped_column(String(5), default="en")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    owner = relationship("User")
    applicants = relationship("Applicant", back_populates="application", cascade="all, delete-orphan", order_by="Applicant.id")
    documents = relationship("Document", back_populates="application", cascade="all, delete-orphan")
    requests = relationship("DocumentRequest", back_populates="application", cascade="all, delete-orphan", order_by="DocumentRequest.id")


class Applicant(Base, Timestamps):
    __tablename__ = "applicants"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="PRIMARY")
    full_name: Mapped[str] = mapped_column(String(200))
    dob: Mapped[date] = mapped_column(Date)
    pan: Mapped[str] = mapped_column(String(10), index=True)
    phone: Mapped[str] = mapped_column(String(15))
    email: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(300), default="")
    city: Mapped[str] = mapped_column(String(80), default="")
    employment_type: Mapped[str] = mapped_column(String(20))
    employer: Mapped[str] = mapped_column(String(200), default="")
    years_in_job: Mapped[float] = mapped_column(Float, default=0)
    monthly_income: Mapped[float] = mapped_column(Float)
    other_income: Mapped[float] = mapped_column(Float, default=0)
    existing_emi: Mapped[float] = mapped_column(Float, default=0)
    business_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    annual_turnover: Mapped[float | None] = mapped_column(Float, nullable=True)
    annual_itr_income: Mapped[float | None] = mapped_column(Float, nullable=True)

    application = relationship("Application", back_populates="applicants")


class DocumentRequest(Base, Timestamps):
    __tablename__ = "document_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    applicant_id: Mapped[int | None] = mapped_column(ForeignKey("applicants.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20))
    item_key: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_reminded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reminders_sent: Mapped[int] = mapped_column(Integer, default=0)
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    application = relationship("Application", back_populates="requests")
