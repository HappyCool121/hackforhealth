from datetime import date, datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

VisitReason = Literal[
    "gp_consultation",
    "corporate_insurer_screening",
    "occupational_health_screening",
    "employer_insurer_medical_exam",
    "healthier_sg_periodic_checkup",
    "other_unsure",
]
DocumentRequirement = Literal["yes", "no", "unsure"]
IdentitySource = Literal["manual", "singpass_demo"]


class LoginRequest(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=255)
    password: str


class CaseCreate(BaseModel):
    patient_name: str = Field(min_length=2, max_length=150)
    patient_email: str = Field(pattern=EMAIL_PATTERN, max_length=255)
    id_last4: str = Field(pattern=r"^[A-Za-z0-9]{4}$")
    appointment_type: Literal["scheduled", "walk-in"]
    appointment_date: date | None = None
    visit_reason: VisitReason = "other_unsure"
    document_requirement: DocumentRequirement = "yes"
    identity_source: IdentitySource = "manual"
    clinic_id: str = "clinic-central"


class CasePatch(BaseModel):
    patient_name: str | None = None
    patient_email: str | None = Field(default=None, pattern=EMAIL_PATTERN, max_length=255)
    id_last4: str | None = Field(default=None, pattern=r"^[A-Za-z0-9]{4}$")
    appointment_date: date | None = None
    visit_reason: VisitReason | None = None
    document_requirement: DocumentRequirement | None = None


class ReviewAction(BaseModel):
    action: Literal["request_information", "approve", "cancel"]
    reason: str = Field(min_length=3, max_length=500)
    override_failures: bool = False


class CheckInRequest(BaseModel):
    identity_checked_on_site: bool
    ecard_checked_on_site: bool
    originals_checked_on_site: bool


class Evidence(BaseModel):
    evidence_id: str
    page: int
    text: str
    bbox: list[float] | None = None


class ExtractedDocument(BaseModel):
    category: Literal[
        "medical_chit",
        "referral",
        "healthier_sg",
        "government_checkup",
        "driver_license_renewal",
        "insurance_ecard",
        "screening_voucher",
        "authorization",
        "unknown",
    ]
    fields: dict[str, Any]
    evidence: list[Evidence]
    warnings: list[str] = []


class AuditOut(BaseModel):
    id: str
    case_id: str | None
    actor_type: str
    actor_id: str | None
    action: str
    details: dict[str, Any]
    created_at: datetime
    model_config = {"from_attributes": True}
