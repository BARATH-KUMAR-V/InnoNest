from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import Timestamps, utcnow


class ProviderCall(Base):
    __tablename__ = "provider_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    applicant_id: Mapped[int | None] = mapped_column(ForeignKey("applicants.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(40), index=True)
    provider_name: Mapped[str] = mapped_column(String(120))
    mode: Mapped[str] = mapped_column(String(20))
    integration_status: Mapped[str] = mapped_column(String(20))
    response_status: Mapped[str] = mapped_column(String(20))
    consent_ref: Mapped[str | None] = mapped_column(String(60), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)
    verification_result: Mapped[str] = mapped_column(String(30))
    response: Mapped[dict] = mapped_column(JSON, default=dict)
    response_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    run: Mapped[int] = mapped_column(Integer, default=1)


class VerificationCheck(Base, Timestamps):
    __tablename__ = "verification_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    applicant_id: Mapped[int | None] = mapped_column(ForeignKey("applicants.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(20), index=True)
    code: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20))
    detail: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    disposition: Mapped[str | None] = mapped_column(String(20), nullable=True)
    disposition_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    disposition_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    run: Mapped[int] = mapped_column(Integer, default=1)


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    run: Mapped[int] = mapped_column(Integer, default=1)
    financial: Mapped[dict] = mapped_column(JSON, default=dict)
    risk: Mapped[dict] = mapped_column(JSON, default=dict)
    property_assessment: Mapped[dict] = mapped_column(JSON, default=dict)
    verification_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    outcome: Mapped[str] = mapped_column(String(10), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="SYSTEM")
    decided_by: Mapped[str] = mapped_column(String(120), default="decision-engine")
    policy_key: Mapped[str] = mapped_column(String(30))
    policy_name: Mapped[str] = mapped_column(String(60))
    policy_version: Mapped[int] = mapped_column(Integer)
    ruleset_version: Mapped[str] = mapped_column(String(30))
    inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    outputs: Mapped[dict] = mapped_column(JSON, default=dict)
    reason_codes: Mapped[list] = mapped_column(JSON, default=list)
    explanation: Mapped[str] = mapped_column(Text, default="")
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    policy_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    result_hash: Mapped[str] = mapped_column(String(64))
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
