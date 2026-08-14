from __future__ import annotations
from datetime import date, datetime, timezone
from uuid import uuid4
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


def uid() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(30))
    clinic_id: Mapped[str] = mapped_column(String(50), default="clinic-central")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class StaffSession(Base):
    __tablename__ = "staff_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship()


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    reference: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    patient_name: Mapped[str] = mapped_column(String(150))
    patient_email: Mapped[str] = mapped_column(String(255))
    id_last4: Mapped[str] = mapped_column(String(4))
    appointment_type: Mapped[str] = mapped_column(String(20))
    appointment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    visit_reason: Mapped[str] = mapped_column(String(50), default="other_unsure")
    document_requirement: Mapped[str] = mapped_column(String(10), default="yes")
    identity_source: Mapped[str] = mapped_column(String(30), default="manual")
    requested_services: Mapped[list] = mapped_column(JSON, default=list)
    clinic_id: Mapped[str] = mapped_column(String(50), default="clinic-central")
    status: Mapped[str] = mapped_column(String(40), default="DRAFT", index=True)
    patient_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    rules: Mapped[list] = mapped_column(JSON, default=list)
    ai_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    check_in_confirmations: Mapped[dict] = mapped_column(JSON, default=dict)
    queue_number: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True, index=True)
    queue_status: Mapped[str] = mapped_column(String(30), default="NOT_ISSUED")
    room_assignment: Mapped[str | None] = mapped_column(String(80), nullable=True)
    queue_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    documents: Mapped[list[Document]] = relationship(back_populates="case", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    expected_category: Mapped[str] = mapped_column(String(40))
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(100))
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_path: Mapped[str] = mapped_column(Text)
    content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)
    status: Mapped[str] = mapped_column(String(30), default="QUEUED")
    scan_status: Mapped[str] = mapped_column(String(30), default="PENDING_SCAN")
    processing_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    extracted_data: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    quality_warnings: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    case: Mapped[Case] = relationship(back_populates="documents")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    previous_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    integrity_digest: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReferenceData(Base):
    __tablename__ = "reference_data"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    code: Mapped[str] = mapped_column(String(60))
    label: Mapped[str] = mapped_column(String(150))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ReferenceDataRelease(Base):
    __tablename__ = "reference_data_releases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    version: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PayerOrganisation(Base):
    __tablename__ = "payer_organisations"
    __table_args__ = (UniqueConstraint("release_id", "code", name="uq_payer_release_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    release_id: Mapped[str] = mapped_column(ForeignKey("reference_data_releases.id"), index=True)
    code: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(180))
    organisation_type: Mapped[str] = mapped_column(String(30))
    issuer_aliases: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class EligibilityContract(Base):
    __tablename__ = "eligibility_contracts"
    __table_args__ = (UniqueConstraint("release_id", "organisation_code", name="uq_contract_release_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    release_id: Mapped[str] = mapped_column(ForeignKey("reference_data_releases.id"), index=True)
    payer_organisation_id: Mapped[str] = mapped_column(ForeignKey("payer_organisations.id"))
    organisation_code: Mapped[str] = mapped_column(String(60), index=True)
    policy_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class PackageVersion(Base):
    __tablename__ = "package_versions"
    __table_args__ = (UniqueConstraint("release_id", "code", name="uq_package_release_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    release_id: Mapped[str] = mapped_column(ForeignKey("reference_data_releases.id"), index=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("eligibility_contracts.id"))
    code: Mapped[str] = mapped_column(String(60), index=True)
    name: Mapped[str] = mapped_column(String(180))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date] = mapped_column(Date)
    required_documents: Mapped[list] = mapped_column(JSON, default=list)
    restrictions: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Procedure(Base):
    __tablename__ = "procedures"
    __table_args__ = (UniqueConstraint("release_id", "code", name="uq_procedure_release_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    release_id: Mapped[str] = mapped_column(ForeignKey("reference_data_releases.id"), index=True)
    code: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(180))
    aliases: Mapped[list] = mapped_column(JSON, default=list)


class PackageProcedure(Base):
    __tablename__ = "package_procedures"
    __table_args__ = (UniqueConstraint("package_version_id", "procedure_id", name="uq_package_procedure"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    package_version_id: Mapped[str] = mapped_column(ForeignKey("package_versions.id"), index=True)
    procedure_id: Mapped[str] = mapped_column(ForeignKey("procedures.id"))
    coverage: Mapped[str] = mapped_column(String(20))
    condition: Mapped[str | None] = mapped_column(Text, nullable=True)


class ClinicPanelRule(Base):
    __tablename__ = "clinic_panel_rules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    release_id: Mapped[str] = mapped_column(ForeignKey("reference_data_releases.id"), index=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("eligibility_contracts.id"))
    clinic_id: Mapped[str] = mapped_column(String(50), index=True)
    location_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    permitted: Mapped[bool] = mapped_column(Boolean, default=True)


class BillingRule(Base):
    __tablename__ = "billing_rules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    release_id: Mapped[str] = mapped_column(ForeignKey("reference_data_releases.id"), index=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("eligibility_contracts.id"))
    package_version_id: Mapped[str | None] = mapped_column(ForeignKey("package_versions.id"), nullable=True)
    payer: Mapped[str] = mapped_column(String(180))
    arrangement: Mapped[str] = mapped_column(String(60))
    billing_code: Mapped[str] = mapped_column(String(60))


class PatientProfile(Base):
    __tablename__ = "patient_profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    identity_type: Mapped[str] = mapped_column(String(30), default="national_id")
    identity_number_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    identity_hash: Mapped[str] = mapped_column(String(64), index=True)
    masked_identity: Mapped[str] = mapped_column(String(20))
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    email: Mapped[str] = mapped_column(String(255))
    country_code: Mapped[str] = mapped_column(String(8), default="+65")
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ethnicity: Mapped[str | None] = mapped_column(String(60), nullable=True)
    sex: Mapped[str | None] = mapped_column(String(30), nullable=True)
    pregnancy_details: Mapped[dict] = mapped_column(JSON, default=dict)
    provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class QuestionnaireSubmission(Base):
    __tablename__ = "questionnaire_submissions"
    __table_args__ = (UniqueConstraint("case_id", "questionnaire_type", name="uq_case_questionnaire"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    questionnaire_type: Mapped[str] = mapped_column(String(50))
    definition_version: Mapped[str] = mapped_column(String(30))
    responses: Mapped[dict] = mapped_column(JSON, default=dict)
    consents: Mapped[dict] = mapped_column(JSON, default=dict)
    signature_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    confirmed_prefill_fields: Mapped[list] = mapped_column(JSON, default=list)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class FieldAssertion(Base):
    __tablename__ = "field_assertions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(100), index=True)
    raw_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    bounding_boxes: Mapped[list] = mapped_column(JSON, default=list)
    extraction_provider: Mapped[str] = mapped_column(String(30))
    support_status: Mapped[str] = mapped_column(String(30), default="UNSUPPORTED")
    validation_errors: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class StaffCorrection(Base):
    __tablename__ = "staff_corrections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    assertion_id: Mapped[str] = mapped_column(ForeignKey("field_assertions.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(100))
    original_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_value: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class EligibilityEvaluation(Base):
    __tablename__ = "eligibility_evaluations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    ruleset_version: Mapped[str] = mapped_column(String(40))
    reference_data_version: Mapped[str] = mapped_column(String(40))
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    outcome: Mapped[str] = mapped_column(String(40))
    stale: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class RuleFinding(Base):
    __tablename__ = "rule_findings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    evaluation_id: Mapped[str] = mapped_column(ForeignKey("eligibility_evaluations.id"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20))
    critical: Mapped[bool] = mapped_column(Boolean, default=True)
    explanation: Mapped[str] = mapped_column(Text)
    evidence_assertion_ids: Mapped[list] = mapped_column(JSON, default=list)
    reference_record_ids: Mapped[list] = mapped_column(JSON, default=list)


class OverrideRequest(Base):
    __tablename__ = "override_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    finding_id: Mapped[str] = mapped_column(ForeignKey("rule_findings.id"), index=True)
    requested_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class FindingOverride(Base):
    __tablename__ = "finding_overrides"
    __table_args__ = (UniqueConstraint("finding_id", name="uq_finding_override"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    finding_id: Mapped[str] = mapped_column(ForeignKey("rule_findings.id"), index=True)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    actor_role: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    evaluation_id: Mapped[str | None] = mapped_column(ForeignKey("eligibility_evaluations.id"), nullable=True)
    decision: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(Text)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class OnSiteAttestation(Base):
    __tablename__ = "on_site_attestations"
    __table_args__ = (UniqueConstraint("case_id", "attestation_type", name="uq_case_attestation"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    attestation_type: Mapped[str] = mapped_column(String(40))
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    attested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class IntegrationExport(Base):
    __tablename__ = "integration_exports"
    __table_args__ = (UniqueConstraint("case_id", "idempotency_key", name="uq_case_idempotency"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    schema_version: Mapped[str] = mapped_column(String(20))
    idempotency_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    request_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    response_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    correlation_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class ProcessingMetric(Base):
    __tablename__ = "processing_metrics"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(30))
    dimensions: Mapped[dict] = mapped_column(JSON, default=dict)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    fixture_manifest_version: Mapped[str] = mapped_column(String(40))
    ruleset_version: Mapped[str] = mapped_column(String(40))
    reference_data_version: Mapped[str] = mapped_column(String(40))
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"
    __table_args__ = (UniqueConstraint("scope", "bucket_key", "window_start", name="uq_rate_limit_bucket"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    scope: Mapped[str] = mapped_column(String(40), index=True)
    bucket_key: Mapped[str] = mapped_column(String(64), index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    count: Mapped[int] = mapped_column(Integer, default=0)


class PatientAccessCode(Base):
    __tablename__ = "patient_access_codes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
