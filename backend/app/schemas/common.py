from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.services.catalog import EMPLOYMENT_TYPES, LAP_END_USES, PROPERTY_TYPES

PAN_PATTERN = r"^[A-Z]{5}[0-9]{4}[A-Z]$"
PHONE_PATTERN = r"^[6-9][0-9]{9}$"


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel):
    items: list
    total: int
    page: int
    page_size: int


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    full_name: str = Field(min_length=2, max_length=120)
    phone: str | None = Field(default=None, pattern=PHONE_PATTERN)


class UserOut(ORM):
    id: int
    email: str
    full_name: str
    role: str
    phone: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ApplicantIn(BaseModel):
    id: int | None = None
    role: Literal["PRIMARY", "CO_APPLICANT"] = "PRIMARY"
    full_name: str = Field(min_length=2, max_length=120)
    dob: date
    pan: str = Field(pattern=PAN_PATTERN)
    phone: str = Field(pattern=PHONE_PATTERN)
    email: EmailStr
    address: str = Field(default="", max_length=300)
    city: str = Field(default="", max_length=80)
    employment_type: Literal["SALARIED", "GOVT", "SELF_EMPLOYED"]
    employer: str = Field(default="", max_length=200)
    years_in_job: float = Field(default=0, ge=0, le=60)
    monthly_income: float = Field(gt=0, le=100_000_000)
    other_income: float = Field(default=0, ge=0)
    existing_emi: float = Field(default=0, ge=0)
    business_type: str | None = None
    annual_turnover: float | None = Field(default=None, ge=0)
    annual_itr_income: float | None = Field(default=None, ge=0)

    @field_validator("pan", mode="before")
    @classmethod
    def upper_pan(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("dob")
    @classmethod
    def adult(cls, value: date):
        if (date.today() - value).days / 365.25 < 18:
            raise ValueError("The applicant must be at least 18 years old")
        if (date.today() - value).days / 365.25 > 90:
            raise ValueError("The date of birth is not plausible")
        return value


class ApplicationCreate(BaseModel):
    product: Literal["HOME_LOAN", "LAP"]
    loan_amount: float = Field(gt=0, le=1_000_000_000)
    interest_rate: float = Field(ge=0, le=40)
    tenure_months: int = Field(ge=1, le=480)
    purpose: str = Field(min_length=2, max_length=60)
    end_use: Literal[LAP_END_USES] | None = None
    policy_key: Literal["balanced", "conservative", "flexible"] = "balanced"
    property_type: Literal[PROPERTY_TYPES]
    property_subtype: Literal["RESIDENTIAL", "COMMERCIAL"] = "RESIDENTIAL"
    property_city: str = Field(min_length=2, max_length=80)
    property_address: str = Field(default="", max_length=300)
    property_pincode: str = Field(default="", pattern=r"^([0-9]{6})?$")
    property_area_sqft: float = Field(default=0, ge=0)
    locality_tier: int = Field(default=2, ge=1, le=3)
    survey_no: str = Field(default="", max_length=60)
    declared_value: float = Field(gt=0)
    seller_name: str | None = None
    owner_name: str | None = None
    existing_mortgage_amount: float = Field(default=0, ge=0)
    under_construction: bool = False
    language: Literal["en", "hi", "ta"] = "en"
    applicants: list[ApplicantIn] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def product_rules(self):
        if self.product == "LAP" and self.property_type == "PLOT" and self.under_construction:
            raise ValueError("A plot cannot be under construction")
        if self.applicants[0].role != "PRIMARY":
            raise ValueError("The first applicant must be the primary applicant")
        if len(self.applicants) == 2 and self.applicants[1].role != "CO_APPLICANT":
            raise ValueError("The second applicant must be a co-applicant")
        if self.loan_amount > self.declared_value * 1.2 and self.product == "HOME_LOAN":
            raise ValueError("The loan amount cannot be far above the property value")
        return self


class ApplicationUpdate(BaseModel):
    loan_amount: float | None = Field(default=None, gt=0)
    interest_rate: float | None = Field(default=None, ge=0, le=40)
    tenure_months: int | None = Field(default=None, ge=1, le=480)
    purpose: str | None = None
    end_use: Literal[LAP_END_USES] | None = None
    property_type: Literal[PROPERTY_TYPES] | None = None
    property_city: str | None = None
    property_address: str | None = None
    property_pincode: str | None = Field(default=None, pattern=r"^([0-9]{6})?$")
    property_area_sqft: float | None = Field(default=None, ge=0)
    survey_no: str | None = None
    declared_value: float | None = Field(default=None, gt=0)
    seller_name: str | None = None
    owner_name: str | None = None
    existing_mortgage_amount: float | None = Field(default=None, ge=0)
    applicants: list[ApplicantIn] | None = None


class ConsentIn(BaseModel):
    scopes: dict[str, bool]


class ClarificationIn(BaseModel):
    request_id: int
    response: str = Field(min_length=5, max_length=1000)


class DispositionIn(BaseModel):
    disposition: Literal["CLEARED", "CONFIRMED"]
    note: str = Field(min_length=10, max_length=1000)


class ReviewIn(BaseModel):
    outcome: Literal["APPROVE", "REJECT"]
    note: str = Field(min_length=10, max_length=1000)


class FieldCorrection(BaseModel):
    value: str = Field(min_length=1, max_length=500)


class EmiIn(BaseModel):
    principal: float
    annual_rate: float
    months: int


class EligibilityIn(BaseModel):
    product: Literal["HOME_LOAN", "LAP"]
    policy_key: Literal["balanced", "conservative", "flexible"] = "balanced"
    employment_type: Literal["SALARIED", "GOVT", "SELF_EMPLOYED"]
    monthly_income: float
    existing_emi: float = 0
    other_income: float = 0
    interest_rate: float
    tenure_months: int
    property_value: float
    loan_amount: float | None = None


class PolicyUpdate(BaseModel):
    params: dict
    change_note: str = Field(min_length=10, max_length=500)


class FollowUpConfig(BaseModel):
    reminder_intervals_hours: list[int] = Field(min_length=1, max_length=6)
    expiry_days: int = Field(ge=1, le=90)

    @field_validator("reminder_intervals_hours")
    @classmethod
    def positive(cls, value):
        if any(v <= 0 for v in value):
            raise ValueError("Reminder intervals must be positive hours")
        return value


class FollowUpRun(BaseModel):
    advance_hours: int = Field(default=0, ge=0, le=24 * 120)


class OutageIn(BaseModel):
    down: bool


class DocumentOut(ORM):
    id: int
    application_id: int
    applicant_id: int | None
    doc_type: str
    detected_type: str | None
    original_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    status: str
    extraction_status: str
    confidence: float | None
    findings: list
    page_count: int
    ocr_used: bool
    uploaded_at: datetime
    metadata_info: dict


class FieldOut(ORM):
    id: int
    name: str
    value: str
    numeric_value: float | None
    confidence: float
    corrected_value: str | None
    effective_value: str


class ApplicantOut(ORM):
    id: int
    role: str
    full_name: str
    dob: date
    pan: str
    phone: str
    email: str
    address: str
    city: str
    employment_type: str
    employer: str
    years_in_job: float
    monthly_income: float
    other_income: float
    existing_emi: float
    business_type: str | None
    annual_turnover: float | None
    annual_itr_income: float | None


class RequestOut(ORM):
    id: int
    kind: str
    item_key: str
    title: str
    message: str
    status: str
    response: str | None
    due_at: datetime | None
    reminders_sent: int
    last_reminded_at: datetime | None
    created_at: datetime
    fulfilled_at: datetime | None


class ApplicationOut(ORM):
    id: int
    reference: str
    owner_id: int
    product: str
    status: str
    pending_stage: str | None
    loan_amount: float
    interest_rate: float
    tenure_months: int
    purpose: str
    end_use: str | None
    policy_key: str
    property_type: str
    property_subtype: str
    property_city: str
    property_address: str
    property_pincode: str
    property_area_sqft: float
    survey_no: str
    declared_value: float
    seller_name: str | None
    owner_name: str | None
    existing_mortgage_amount: float
    consents: dict
    language: str
    submitted_at: datetime | None
    decided_at: datetime | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    applicants: list[ApplicantOut]


class ApplicationRow(ORM):
    id: int
    reference: str
    product: str
    status: str
    loan_amount: float
    property_city: str
    policy_key: str
    submitted_at: datetime | None
    decided_at: datetime | None
    created_at: datetime
    applicant_name: str | None = None
    employment_type: str | None = None


class NotificationOut(ORM):
    id: int
    application_id: int | None
    channel: str
    kind: str
    subject: str
    body: str
    delivery_status: str
    simulated: bool
    recipient: str | None
    read_at: datetime | None
    created_at: datetime


class CheckOut(ORM):
    id: int
    applicant_id: int | None
    category: str
    code: str
    title: str
    status: str
    detail: str
    evidence: dict
    disposition: str | None
    disposition_note: str | None
    run: int


class ProviderCallOut(ORM):
    id: int
    applicant_id: int | None
    provider: str
    provider_name: str
    mode: str
    integration_status: str
    response_status: str
    consent_ref: str | None
    source_ref: str | None
    verification_result: str
    response: dict
    response_hash: str | None
    requested_at: datetime
    run: int


class PolicyOut(ORM):
    id: int
    key: str
    name: str
    version: int
    status: str
    description: str
    params: dict
    change_note: str | None
    created_by: str
    created_at: datetime


class DecisionOut(ORM):
    id: int
    application_id: int
    outcome: str
    kind: str
    decided_by: str
    policy_key: str
    policy_name: str
    policy_version: int
    ruleset_version: str
    inputs: dict
    outputs: dict
    reason_codes: list
    explanation: str
    evidence_refs: list
    result_hash: str
    review_note: str | None
    created_at: datetime


class AuditOut(ORM):
    id: int
    application_id: int | None
    actor: str
    actor_role: str
    action: str
    entity: str | None
    entity_id: int | None
    details: dict
    prev_hash: str
    hash: str
    created_at: datetime
