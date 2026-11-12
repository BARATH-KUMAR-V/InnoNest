from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import Timestamps, utcnow


class Document(Base, Timestamps):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    applicant_id: Mapped[int | None] = mapped_column(ForeignKey("applicants.id"), nullable=True)
    doc_type: Mapped[str] = mapped_column(String(40), index=True)
    detected_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    original_name: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(60))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20), default="UPLOADED", index=True)
    extraction_status: Mapped[str] = mapped_column(String(30), default="PENDING")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    text_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    findings: Mapped[list] = mapped_column(JSON, default=list)
    metadata_info: Mapped[dict] = mapped_column(JSON, default=dict)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    ocr_used: Mapped[bool] = mapped_column(default=False)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    superseded_by: Mapped[int | None] = mapped_column(Integer, nullable=True)

    application = relationship("Application", back_populates="documents")
    fields = relationship("ExtractedField", back_populates="document", cascade="all, delete-orphan", order_by="ExtractedField.id")


class ExtractedField(Base, Timestamps):
    __tablename__ = "extracted_fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    value: Mapped[str] = mapped_column(String(500))
    numeric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float)
    corrected_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    corrected_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    document = relationship("Document", back_populates="fields")

    @property
    def effective_value(self) -> str:
        return self.corrected_value if self.corrected_value is not None else self.value

    @property
    def effective_numeric(self) -> float | None:
        if self.corrected_value is None:
            return self.numeric_value
        cleaned = self.corrected_value.replace("INR", "").replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
