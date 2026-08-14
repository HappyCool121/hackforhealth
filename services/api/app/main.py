from __future__ import annotations
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import secrets
import smtplib
from email.message import EmailMessage
import httpx
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, Depends, FastAPI, File, Form, Header, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .auth import create_session, current_staff, hash_token, manager_only, ph
from .config import get_settings
from .db import Base, SessionLocal, engine, get_db
from .eligibility import current_input_hash, evaluate_case, invalidate_evaluations, latest_evaluation, serialize_evaluation
from .models import (
    AuditEvent,
    BenchmarkRun,
    BillingRule,
    Case,
    Document,
    EligibilityContract,
    EligibilityEvaluation,
    FieldAssertion,
    FindingOverride,
    IntegrationExport,
    OnSiteAttestation,
    OverrideRequest,
    ClinicPanelRule,
    PackageProcedure,
    PackageVersion,
    PatientAccessCode,
    PatientProfile,
    PayerOrganisation,
    ProcessingMetric,
    Procedure,
    QuestionnaireSubmission,
    ReferenceData,
    ReferenceDataRelease,
    ReviewDecision,
    RuleFinding,
    StaffCorrection,
    StaffSession,
    User,
)
from .ocr import inspect_upload
from .processing import finalize_case_if_ready
from .reference_seed import backfill_v2, seed_v2_reference_data
from .questionnaires import QUESTIONNAIRE_DEFINITIONS
from .schemas import (
    AttestationCreate,
    CaseCreate,
    CasePatch,
    CheckInRequest,
    CorrectionPatch,
    LoginRequest,
    OverrideCreate,
    OverrideRequestCreate,
    PatientAccessRequest,
    PatientProfilePatch,
    QuestionnairePut,
    ReviewAction,
)
from .security import (
    append_audit,
    backfill_audit_chain,
    encrypt_identity,
    get_upload_scanner,
    identity_hash,
    issue_csrf,
    mask_identity,
    rate_limit,
    verify_audit_chain,
    verify_csrf,
)


settings = get_settings()
ALLOWED_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/jpg", "image/heic", "image/heif"}
ALLOWED_CATEGORIES = {
    "medical_chit",
    "referral",
    "healthier_sg",
    "government_checkup",
    "driver_license_renewal",
    "insurance_ecard",
    "screening_voucher",
    "authorization",
    "unknown",
}
TRANSITIONS = {
    "DRAFT": {"SUBMITTED", "CANCELLED"},
    "SUBMITTED": {"PROCESSING", "CANCELLED"},
    "PROCESSING": {"NEEDS_ACTION", "READY_FOR_REVIEW", "CANCELLED"},
    "NEEDS_ACTION": {"SUBMITTED", "READY_FOR_REVIEW", "CANCELLED"},
    "READY_FOR_REVIEW": {"NEEDS_ACTION", "APPROVED_FOR_CHECK_IN", "CANCELLED"},
    "APPROVED_FOR_CHECK_IN": {"CHECKED_IN", "CANCELLED"},
    "CHECKED_IN": {"EXPORTED", "COMPLETED"},
    "EXPORTED": {"COMPLETED"},
}


def seed(db: Session) -> None:
    users = [
        (settings.staff_assistant_email, "Clinic Assistant", "assistant", settings.staff_assistant_password),
        (settings.staff_manager_email, "Clinic Manager", "manager", settings.staff_manager_password),
    ]
    for email, name, role, password in users:
        normalized_email = email.lower()
        user = db.scalar(select(User).where(User.email == normalized_email))
        if not user:
            db.add(User(email=normalized_email, name=name, role=role, password_hash=ph.hash(password)))
            continue
        user.name = name
        user.role = role
        password_matches: bool
        try:
            password_matches = ph.verify(user.password_hash, password)
        except VerifyMismatchError:
            password_matches = False
        if not password_matches or ph.check_needs_rehash(user.password_hash):
            user.password_hash = ph.hash(password)
    references = [
        ("clinic", "clinic-central", "Central Family Clinic"),
        ("organization", "ORG-DEMO", "Demo Health Organisation"),
        ("package", "PKG-SCREEN", "Preventive Screening Package"),
    ]
    for kind, code, label in references:
        exists = db.scalar(select(ReferenceData).where(ReferenceData.kind == kind, ReferenceData.code == code))
        if not exists:
            db.add(ReferenceData(kind=kind, code=code, label=label))
    db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
        if settings.clinicpass_v2_enabled:
            seed_v2_reference_data(db)
            backfill_v2(db)
            backfill_audit_chain(db)
            db.commit()
    yield


app = FastAPI(
    title="ClinicPass API",
    version="2.0.0",
    description="Administrative pre-registration and eligibility-readiness API. Not for clinical decisions or coverage guarantees.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)


@app.middleware("http")
async def require_gateway_secret(request: Request, call_next):
    if request.url.path == "/health" or not settings.backend_gateway_secret:
        return await call_next(request)
    supplied = request.headers.get("x-clinicpass-gateway", "")
    if not secrets.compare_digest(supplied, settings.backend_gateway_secret):
        return JSONResponse(status_code=401, content={"detail": "Gateway authentication required"})
    return await call_next(request)


@app.middleware("http")
async def protect_staff_mutations(request: Request, call_next):
    try:
        verify_csrf(request)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)


def audit(db: Session, case_id: str | None, actor_type: str, actor_id: str | None, action: str, details: dict | None = None) -> None:
    append_audit(db, case_id, actor_type, actor_id, action, details)


def transition(case: Case, target: str) -> None:
    if target not in TRANSITIONS.get(case.status, set()):
        raise HTTPException(409, f"Cannot transition case from {case.status} to {target}")
    case.status = target


def issue_queue(case: Case) -> None:
    if not case.queue_number:
        case.queue_number = f"Q{int(case.id.replace('-', ''), 16) % 100_000_000:08d}"
    case.queue_status = "WAITING_FOR_REVIEW"
    case.room_assignment = "Waiting area"
    case.queue_updated_at = datetime.now(timezone.utc)


def update_queue(case: Case, status: str, room: str) -> None:
    case.queue_status = status
    case.room_assignment = room
    case.queue_updated_at = datetime.now(timezone.utc)


def case_query():
    return select(Case).options(selectinload(Case.documents))


def serialize_document(doc: Document, include_evidence: bool = True) -> dict:
    patient_summary_keys = {
        "document_title",
        "issuer",
        "valid_from",
        "valid_to",
        "checkup_frequency",
        "preparation_instructions",
        "supporting_document_note",
    }
    result = {
        "id": doc.id,
        "expected_category": doc.expected_category,
        "category": doc.category,
        "filename": doc.filename,
        "media_type": doc.media_type,
        "page_count": doc.page_count,
        "sha256": doc.sha256,
        "status": doc.status,
        "scan_status": doc.scan_status,
        "processing_provider": doc.processing_provider,
        "extracted_data": doc.extracted_data,
        "patient_summary": {
            key: value for key, value in (doc.extracted_data or {}).items() if key in patient_summary_keys and value
        },
        "quality_warnings": doc.quality_warnings,
        "error": doc.error,
    }
    if include_evidence:
        result["evidence"] = doc.evidence
    return result


def serialize_assertion(assertion: FieldAssertion, correction: StaffCorrection | None = None) -> dict:
    return {
        "id": assertion.id,
        "field_name": assertion.field_name,
        "raw_value": assertion.raw_value,
        "normalized_value": correction.corrected_value if correction else assertion.normalized_value,
        "original_normalized_value": assertion.normalized_value,
        "document_id": assertion.document_id,
        "page": assertion.page,
        "evidence_ids": assertion.evidence_ids,
        "bounding_boxes": assertion.bounding_boxes,
        "extraction_provider": assertion.extraction_provider,
        "support_status": "STAFF_CORRECTED" if correction else assertion.support_status,
        "validation_errors": assertion.validation_errors,
        "correction": {
            "id": correction.id,
            "reason": correction.reason,
            "actor_user_id": correction.actor_user_id,
            "created_at": correction.created_at.isoformat(),
        } if correction else None,
    }


def serialize_profile(profile: PatientProfile | None) -> dict | None:
    if not profile:
        return None
    return {
        "full_name": profile.full_name,
        "identity_type": profile.identity_type,
        "masked_identity": profile.masked_identity,
        "date_of_birth": profile.date_of_birth.isoformat() if profile.date_of_birth else None,
        "email": profile.email,
        "country_code": profile.country_code,
        "phone": profile.phone,
        "address": profile.address,
        "postal_code": profile.postal_code,
        "ethnicity": profile.ethnicity,
        "sex": profile.sex,
        "pregnancy_details": profile.pregnancy_details,
        "provider": profile.provider,
        "confirmed_at": profile.confirmed_at.isoformat() if profile.confirmed_at else None,
    }


def serialize_case(case: Case, detail: bool = True, db: Session | None = None) -> dict:
    result = {
        "id": case.id,
        "reference": case.reference,
        "patient_name": case.patient_name,
        "patient_email": case.patient_email,
        "id_last4": case.id_last4,
        "appointment_type": case.appointment_type,
        "appointment_date": case.appointment_date.isoformat() if case.appointment_date else None,
        "visit_reason": case.visit_reason,
        "document_requirement": case.document_requirement,
        "identity_source": case.identity_source,
        "requested_services": case.requested_services or [],
        "clinic_id": case.clinic_id,
        "status": case.status,
        "rules": case.rules,
        "ai_provider": case.ai_provider,
        "check_in_confirmations": case.check_in_confirmations,
        "queue_number": case.queue_number,
        "queue_status": case.queue_status,
        "room_assignment": case.room_assignment,
        "queue_updated_at": case.queue_updated_at.isoformat() if case.queue_updated_at else None,
        "created_at": case.created_at.isoformat(),
        "updated_at": case.updated_at.isoformat(),
    }
    if detail:
        result["documents"] = [serialize_document(doc) for doc in case.documents]
        if db is not None and settings.clinicpass_v2_enabled:
            profile = db.scalar(select(PatientProfile).where(PatientProfile.case_id == case.id))
            assertions = db.scalars(select(FieldAssertion).where(FieldAssertion.case_id == case.id).order_by(FieldAssertion.created_at)).all()
            corrections = {
                item.assertion_id: item
                for item in db.scalars(select(StaffCorrection).where(StaffCorrection.case_id == case.id).order_by(StaffCorrection.created_at)).all()
            }
            questionnaires = db.scalars(select(QuestionnaireSubmission).where(QuestionnaireSubmission.case_id == case.id)).all()
            result["profile"] = serialize_profile(profile)
            result["assertions"] = [serialize_assertion(item, corrections.get(item.id)) for item in assertions]
            result["questionnaires"] = [
                {
                    "type": item.questionnaire_type,
                    "definition_version": item.definition_version,
                    "responses": item.responses,
                    "consents": item.consents,
                    "signature_metadata": item.signature_metadata,
                    "confirmed_prefill_fields": item.confirmed_prefill_fields,
                }
                for item in questionnaires
            ]
            evaluation = latest_evaluation(db, case.id)
            result["evaluation"] = serialize_evaluation(db, evaluation) if evaluation else None
            result["attestations"] = [
                {"type": item.attestation_type, "actor_user_id": item.actor_user_id, "attested_at": item.attested_at.isoformat()}
                for item in db.scalars(select(OnSiteAttestation).where(OnSiteAttestation.case_id == case.id)).all()
            ]
    return result


def patient_case(db: Session, case_id: str, token: str | None) -> Case:
    case = db.scalar(case_query().where(Case.id == case_id))
    if not case or not token or not secrets.compare_digest(case.patient_token_hash, hash_token(token)):
        raise HTTPException(404, "Case not found")
    return case


def notify(email: str, subject: str, text: str) -> None:
    if not settings.smtp_enabled:
        return
    message = EmailMessage()
    message["From"] = "demo@clinicpass.test"
    message["To"] = email
    message["Subject"] = subject
    message.set_content(text)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=3) as server:
            server.send_message(message)
    except OSError:
        pass


@app.get("/health", include_in_schema=False)
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/v1/health")
def api_health() -> dict:
    return {"status": "ok", "ai_provider": settings.ai_provider}


@app.post("/api/v1/auth/login")
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    rate_limit(db, "login", f"{request.client.host if request.client else 'unknown'}:{payload.email.lower()}", 5, 60)
    db.commit()
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    try:
        valid = bool(user and ph.verify(user.password_hash, payload.password))
    except VerifyMismatchError:
        valid = False
    if not valid or not user or not user.active:
        raise HTTPException(401, "Invalid email or password")
    session_token = create_session(db, user, response)
    issue_csrf(response, session_token)
    audit(db, None, "staff", user.id, "auth.login")
    db.commit()
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "clinic_id": user.clinic_id}


@app.post("/api/v1/auth/logout")
def logout(response: Response, cp_staff: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> dict:
    if cp_staff:
        session = db.scalar(select(StaffSession).where(StaffSession.token_hash == hash_token(cp_staff)))
        if session:
            db.delete(session)
            db.commit()
    response.delete_cookie("cp_staff", path="/")
    response.delete_cookie("cp_csrf", path="/")
    return {"ok": True}


@app.get("/api/v1/auth/me")
def me(user: User = Depends(current_staff)) -> dict:
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "clinic_id": user.clinic_id}


@app.post("/api/v1/patient/cases", status_code=201)
def create_case(payload: CaseCreate, response: Response, db: Session = Depends(get_db)) -> dict:
    if payload.appointment_type == "scheduled" and not payload.appointment_date:
        raise HTTPException(422, "Scheduled visits require an appointment date")
    raw_token = secrets.token_urlsafe(32)
    case = Case(
        reference=f"CP-{datetime.now(timezone.utc):%y%m%d}-{secrets.token_hex(2).upper()}",
        patient_name=payload.patient_name.strip(),
        patient_email=str(payload.patient_email).lower(),
        id_last4=payload.id_last4.upper(),
        appointment_type=payload.appointment_type,
        appointment_date=payload.appointment_date,
        visit_reason=payload.visit_reason,
        document_requirement=payload.document_requirement,
        identity_source=payload.identity_source,
        requested_services=[item.strip().upper() for item in payload.requested_services if item.strip()],
        clinic_id=payload.clinic_id,
        patient_token_hash=hash_token(raw_token),
    )
    db.add(case)
    db.flush()
    bootstrap_code = secrets.token_urlsafe(32)
    if settings.clinicpass_v2_enabled:
        db.add(PatientProfile(
            case_id=case.id,
            full_name=case.patient_name,
            identity_type="national_id_fragment",
            identity_number_encrypted=None,
            identity_hash=identity_hash(payload.id_last4),
            masked_identity=mask_identity(payload.id_last4),
            email=case.patient_email,
            provider=case.identity_source,
        ))
        db.add(PatientAccessCode(
            case_id=case.id,
            code_hash=hash_token(bootstrap_code),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        ))
    audit(db, case.id, "patient", "self", "case.created")
    db.commit()
    response.set_cookie(
        "cp_patient",
        raw_token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=7 * 86400,
        path="/",
    )
    result = serialize_case(case, db=db)
    result["access_url"] = f"{settings.public_base_url}/patient/case/{case.id}"
    result["bootstrap_code"] = bootstrap_code
    return result


@app.post("/api/v1/patient/cases/{case_id}/access")
def access_case(case_id: str, payload: PatientAccessRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    rate_limit(db, "patient_access", request.client.host if request.client else "unknown", 10, 60)
    access = db.scalar(select(PatientAccessCode).where(
        PatientAccessCode.case_id == case_id,
        PatientAccessCode.code_hash == hash_token(payload.bootstrap_code),
        PatientAccessCode.consumed_at.is_(None),
    ))
    now = datetime.now(timezone.utc)
    if not access or access.expires_at.replace(tzinfo=timezone.utc) < now:
        db.commit()
        raise HTTPException(404, "Case not found")
    case = db.scalar(case_query().where(Case.id == case_id))
    if not case:
        raise HTTPException(404, "Case not found")
    rotated_token = secrets.token_urlsafe(32)
    case.patient_token_hash = hash_token(rotated_token)
    access.consumed_at = now
    response.set_cookie(
        "cp_patient",
        rotated_token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=7 * 86400,
        path="/",
    )
    audit(db, case.id, "patient", "link", "case.accessed", {"token_rotated": True})
    db.commit()
    return serialize_case(case, db=db)


@app.get("/api/v1/patient/cases/{case_id}")
def get_patient_case(case_id: str, cp_patient: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> dict:
    return serialize_case(patient_case(db, case_id, cp_patient), db=db)


@app.patch("/api/v1/patient/cases/{case_id}")
def update_patient_case(case_id: str, payload: CasePatch, cp_patient: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> dict:
    case = patient_case(db, case_id, cp_patient)
    if case.status not in {"DRAFT", "NEEDS_ACTION"}:
        raise HTTPException(409, "Case details cannot be edited in the current state")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(case, key, value)
    invalidate_evaluations(db, case.id)
    audit(db, case.id, "patient", "self", "case.updated", {"fields": list(payload.model_dump(exclude_unset=True))})
    db.commit()
    return serialize_case(case, db=db)


@app.patch("/api/v1/patient/cases/{case_id}/profile")
def update_patient_profile(
    case_id: str,
    payload: PatientProfilePatch,
    cp_patient: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> dict:
    case = patient_case(db, case_id, cp_patient)
    if case.status not in {"DRAFT", "NEEDS_ACTION"}:
        raise HTTPException(409, "Profile cannot be edited in the current state")
    profile = db.scalar(select(PatientProfile).where(PatientProfile.case_id == case.id))
    if not profile:
        profile = PatientProfile(
            case_id=case.id,
            full_name=case.patient_name,
            identity_hash=identity_hash(case.id_last4),
            masked_identity=mask_identity(case.id_last4),
            email=case.patient_email,
            provider=case.identity_source,
        )
        db.add(profile)
    values = payload.model_dump(exclude_unset=True, exclude={"identity_number", "confirmed"})
    for key, value in values.items():
        setattr(profile, key, value)
    if payload.identity_number:
        profile.identity_number_encrypted = encrypt_identity(payload.identity_number)
        profile.identity_hash = identity_hash(payload.identity_number)
        profile.masked_identity = mask_identity(payload.identity_number)
        case.id_last4 = payload.identity_number[-4:].upper()
    if payload.full_name:
        case.patient_name = payload.full_name.strip()
    if payload.email:
        case.patient_email = payload.email.lower()
    if payload.confirmed:
        profile.confirmed_at = datetime.now(timezone.utc)
    invalidate_evaluations(db, case.id)
    audit(db, case.id, "patient", "self", "profile.updated", {"fields": sorted(payload.model_fields_set - {"identity_number"}), "identity_changed": bool(payload.identity_number)})
    db.commit()
    return serialize_profile(profile) or {}


@app.put("/api/v1/patient/cases/{case_id}/questionnaires/{questionnaire_type}")
def put_questionnaire(
    case_id: str,
    questionnaire_type: str,
    payload: QuestionnairePut,
    cp_patient: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> dict:
    case = patient_case(db, case_id, cp_patient)
    if case.status not in {"DRAFT", "NEEDS_ACTION"}:
        raise HTTPException(409, "Questionnaire cannot be edited in the current state")
    if questionnaire_type not in {"general-health", "occupational-health"}:
        raise HTTPException(404, "Questionnaire definition not found")
    definition = QUESTIONNAIRE_DEFINITIONS[questionnaire_type]
    unknown_fields = set(payload.responses) - set(definition["response_fields"])
    if unknown_fields:
        raise HTTPException(422, f"Unsupported questionnaire fields: {', '.join(sorted(unknown_fields))}")
    missing_consents = [key for key in definition["required_consents"] if not payload.consents.get(key)]
    if missing_consents:
        raise HTTPException(422, f"Required consents are missing: {', '.join(missing_consents)}")
    if not payload.signature_metadata.get("signed_at") or not payload.signature_metadata.get("method"):
        raise HTTPException(422, "Signature metadata is required")
    item = db.scalar(select(QuestionnaireSubmission).where(
        QuestionnaireSubmission.case_id == case.id,
        QuestionnaireSubmission.questionnaire_type == questionnaire_type,
    ))
    if not item:
        item = QuestionnaireSubmission(case_id=case.id, questionnaire_type=questionnaire_type, definition_version=payload.definition_version)
        db.add(item)
    item.definition_version = payload.definition_version
    item.responses = payload.responses
    item.consents = payload.consents
    item.signature_metadata = payload.signature_metadata
    item.confirmed_prefill_fields = payload.confirmed_prefill_fields
    item.submitted_at = datetime.now(timezone.utc)
    invalidate_evaluations(db, case.id)
    audit(db, case.id, "patient", "self", "questionnaire.saved", {"type": questionnaire_type, "version": payload.definition_version, "prefill_count": len(payload.confirmed_prefill_fields)})
    db.commit()
    return {"type": questionnaire_type, "definition_version": item.definition_version, "saved": True}


@app.get("/api/v1/patient/questionnaires/definitions/{questionnaire_type}")
def get_questionnaire_definition(questionnaire_type: str) -> dict:
    definition = QUESTIONNAIRE_DEFINITIONS.get(questionnaire_type)
    if not definition:
        raise HTTPException(404, "Questionnaire definition not found")
    return definition


@app.post("/api/v1/patient/cases/{case_id}/documents", status_code=201)
async def upload_document(
    case_id: str,
    request: Request,
    category: str | None = Form(default=None),
    file: UploadFile = File(),
    cp_patient: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> dict:
    case = patient_case(db, case_id, cp_patient)
    rate_limit(db, "upload", f"{case.id}:{request.client.host if request.client else 'unknown'}", 10, 600)
    if case.status not in {"DRAFT", "NEEDS_ACTION"}:
        raise HTTPException(409, "Documents cannot be added in the current state")
    if category is not None and category not in ALLOWED_CATEGORIES:
        raise HTTPException(422, "Unsupported document category")
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, "Upload a PDF, PNG, JPEG, HEIC, or HEIF file")
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(413, f"File exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB limit")
    safe_filename = Path(file.filename or "upload").name
    try:
        page_count = inspect_upload(
            content,
            file.content_type or "application/octet-stream",
            safe_filename,
            settings.max_document_pages,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        clean, scan_message = get_upload_scanner().scan(content, safe_filename, file.content_type or "application/octet-stream")
    except Exception as exc:
        if settings.upload_scan_required:
            raise HTTPException(503, "Upload scanning is unavailable") from exc
        clean, scan_message = True, "Scanner bypassed by explicit non-production configuration"
    if not clean:
        audit(db, case.id, "patient", "self", "document.rejected_by_scanner", {"reason": scan_message})
        db.commit()
        raise HTTPException(422, "Upload failed security scanning")
    suffix = Path(file.filename or "upload").suffix.lower()[:8]
    document_id = secrets.token_hex(16)
    destination = Path(settings.upload_dir) / f"{document_id}{suffix}"
    destination.write_bytes(content)
    expected_category = category or "unknown"
    doc = Document(
        id=document_id,
        case_id=case.id,
        expected_category=expected_category,
        filename=safe_filename,
        media_type=file.content_type or "application/octet-stream",
        page_count=page_count,
        sha256=hashlib.sha256(content).hexdigest(),
        storage_path=str(destination),
        content=content,
        scan_status="CLEAN",
    )
    db.add(doc)
    if case.status == "NEEDS_ACTION":
        case.rules = []
    invalidate_evaluations(db, case.id)
    audit(
        db,
        case.id,
        "patient",
        "self",
        "document.uploaded",
        {"document_id": doc.id, "category_hint": expected_category, "page_count": page_count, "scanner": get_upload_scanner().name},
    )
    db.commit()
    return serialize_document(doc)


@app.delete("/api/v1/patient/cases/{case_id}/documents/{document_id}", status_code=204)
def delete_document(
    case_id: str,
    document_id: str,
    cp_patient: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> Response:
    case = patient_case(db, case_id, cp_patient)
    if case.status not in {"DRAFT", "NEEDS_ACTION"}:
        raise HTTPException(409, "Documents cannot be removed in the current state")
    document = next((item for item in case.documents if item.id == document_id), None)
    if not document:
        raise HTTPException(404, "Document not found")
    if document.status == "PROCESSING":
        raise HTTPException(409, "Wait for document processing to finish before removing it")
    storage_path = Path(document.storage_path)
    db.delete(document)
    case.rules = []
    invalidate_evaluations(db, case.id)
    audit(db, case.id, "patient", "self", "document.removed", {"document_id": document.id})
    db.commit()
    try:
        storage_path.unlink(missing_ok=True)
    except OSError:
        pass
    return Response(status_code=204)


@app.post("/api/v1/patient/cases/{case_id}/documents/{document_id}/retry")
def retry_document(
    case_id: str,
    document_id: str,
    request: Request,
    cp_patient: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> dict:
    case = patient_case(db, case_id, cp_patient)
    rate_limit(db, "retry", f"{case.id}:{request.client.host if request.client else 'unknown'}", 5, 600)
    if case.status not in {"DRAFT", "NEEDS_ACTION"}:
        raise HTTPException(409, "Documents cannot be retried in the current state")
    document = next((item for item in case.documents if item.id == document_id), None)
    if not document:
        raise HTTPException(404, "Document not found")
    if document.status != "ERROR":
        raise HTTPException(409, "Only failed documents can be retried")
    document.status = "QUEUED"
    document.category = None
    document.extracted_data = {}
    document.evidence = []
    document.quality_warnings = []
    document.error = None
    document.processing_provider = None
    case.rules = []
    invalidate_evaluations(db, case.id)
    audit(db, case.id, "patient", "self", "document.retried", {"document_id": document.id})
    db.commit()
    return serialize_document(document)


@app.post("/api/v1/patient/cases/{case_id}/submit")
def submit_case(case_id: str, cp_patient: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> dict:
    case = patient_case(db, case_id, cp_patient)
    if case.document_requirement == "yes" and not case.documents:
        raise HTTPException(409, "You indicated documents are needed; upload at least one supporting document")
    if case.document_requirement == "yes" and all(document.status == "ERROR" for document in case.documents):
        raise HTTPException(409, "Retry a failed document or upload a replacement before submitting")
    if settings.clinicpass_v2_enabled:
        profile = db.scalar(select(PatientProfile).where(PatientProfile.case_id == case.id))
        questionnaire = db.scalar(select(QuestionnaireSubmission).where(QuestionnaireSubmission.case_id == case.id))
        if not profile or not profile.confirmed_at:
            raise HTTPException(409, "Confirm the reusable patient profile before submitting")
        if not questionnaire:
            raise HTTPException(409, "Complete the required questionnaire before submitting")
    transition(case, "SUBMITTED")
    issue_queue(case)
    transition(case, "PROCESSING")
    finalize_case_if_ready(case, db)
    audit(db, case.id, "patient", "self", "case.submitted")
    db.commit()
    notify(case.patient_email, f"ClinicPass {case.reference} submitted", "Your synthetic demo registration was submitted for administrative review.")
    return serialize_case(case, db=db)


@app.get("/api/v1/clinic/cases")
def list_cases(status: str | None = None, search: str | None = None, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> list[dict]:
    query = case_query().where(Case.clinic_id == user.clinic_id).order_by(Case.updated_at.desc())
    if status:
        query = query.where(Case.status == status)
    if search:
        query = query.where(Case.patient_name.ilike(f"%{search}%") | Case.reference.ilike(f"%{search}%"))
    return [serialize_case(case, detail=False, db=db) for case in db.scalars(query).all()]


@app.get("/api/v1/clinic/cases/{case_id}")
def get_staff_case(case_id: str, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
    case = db.scalar(case_query().where(Case.id == case_id, Case.clinic_id == user.clinic_id))
    if not case:
        raise HTTPException(404, "Case not found")
    audit(db, case.id, "staff", user.id, "case.viewed")
    db.commit()
    return serialize_case(case, db=db)


@app.get("/api/v1/clinic/cases/{case_id}/documents/{document_id}/page/{page_number}")
def get_document_page(
    case_id: str,
    document_id: str,
    page_number: int,
    user: User = Depends(current_staff),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    document = db.scalar(
        select(Document)
        .join(Case, Case.id == Document.case_id)
        .where(Document.id == document_id, Document.case_id == case_id, Case.clinic_id == user.clinic_id)
    )
    if not document or page_number < 1 or page_number > document.page_count:
        raise HTTPException(404, "Document page not found")
    if document.content is None:
        raise HTTPException(410, "Document content is no longer retained")
    audit(db, case_id, "staff", user.id, "document.page_viewed", {"document_id": document_id, "page": page_number})
    db.commit()
    return StreamingResponse(iter([document.content]), media_type=document.media_type, headers={
        "Content-Disposition": f'inline; filename="{Path(document.filename).name}"',
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    })


@app.get("/api/v1/clinic/cases/{case_id}/evaluation")
def get_case_evaluation(case_id: str, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
    case = db.scalar(case_query().where(Case.id == case_id, Case.clinic_id == user.clinic_id))
    if not case:
        raise HTTPException(404, "Case not found")
    evaluation = latest_evaluation(db, case.id)
    input_hash = current_input_hash(db, case)
    if not evaluation or evaluation.stale or evaluation.input_hash != input_hash:
        evaluation = evaluate_case(db, case)
        db.commit()
    result = serialize_evaluation(db, evaluation)
    result["current_input_hash"] = input_hash
    return result


@app.patch("/api/v1/clinic/cases/{case_id}/assertions/{assertion_id}")
def correct_assertion(
    case_id: str,
    assertion_id: str,
    payload: CorrectionPatch,
    user: User = Depends(current_staff),
    db: Session = Depends(get_db),
) -> dict:
    assertion = db.scalar(
        select(FieldAssertion)
        .join(Case, Case.id == FieldAssertion.case_id)
        .where(FieldAssertion.id == assertion_id, FieldAssertion.case_id == case_id, Case.clinic_id == user.clinic_id)
    )
    if not assertion:
        raise HTTPException(404, "Field assertion not found")
    correction = StaffCorrection(
        case_id=case_id,
        assertion_id=assertion.id,
        field_name=assertion.field_name,
        original_value=assertion.normalized_value,
        corrected_value=payload.corrected_value.strip(),
        reason=payload.reason.strip(),
        actor_user_id=user.id,
    )
    db.add(correction)
    invalidate_evaluations(db, case_id)
    audit(db, case_id, "staff", user.id, "assertion.corrected", {"assertion_id": assertion.id, "field_name": assertion.field_name, "reason": payload.reason})
    db.commit()
    return serialize_assertion(assertion, correction)


@app.post("/api/v1/clinic/cases/{case_id}/override-requests", status_code=201)
def request_override(
    case_id: str,
    payload: OverrideRequestCreate,
    user: User = Depends(current_staff),
    db: Session = Depends(get_db),
) -> dict:
    finding = db.scalar(
        select(RuleFinding)
        .join(EligibilityEvaluation, EligibilityEvaluation.id == RuleFinding.evaluation_id)
        .join(Case, Case.id == EligibilityEvaluation.case_id)
        .where(RuleFinding.id == payload.finding_id, EligibilityEvaluation.case_id == case_id, Case.clinic_id == user.clinic_id)
    )
    if not finding or finding.status == "PASS":
        raise HTTPException(404, "Review finding not found")
    item = OverrideRequest(case_id=case_id, finding_id=finding.id, requested_by_user_id=user.id, reason=payload.reason)
    db.add(item)
    audit(db, case_id, "staff", user.id, "override.requested", {"finding_id": finding.id, "reason": payload.reason})
    db.commit()
    return {"id": item.id, "status": item.status, "finding_id": item.finding_id}


@app.post("/api/v1/clinic/cases/{case_id}/overrides", status_code=201)
def create_override(
    case_id: str,
    payload: OverrideCreate,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
) -> dict:
    finding = db.scalar(
        select(RuleFinding)
        .join(EligibilityEvaluation, EligibilityEvaluation.id == RuleFinding.evaluation_id)
        .join(Case, Case.id == EligibilityEvaluation.case_id)
        .where(RuleFinding.id == payload.finding_id, EligibilityEvaluation.case_id == case_id, Case.clinic_id == user.clinic_id)
    )
    if not finding or finding.status == "PASS":
        raise HTTPException(404, "Review finding not found")
    if db.scalar(select(FindingOverride).where(FindingOverride.finding_id == finding.id)):
        raise HTTPException(409, "Finding already has a manager override")
    override = FindingOverride(
        case_id=case_id,
        finding_id=finding.id,
        actor_user_id=user.id,
        actor_role=user.role,
        reason=payload.reason,
    )
    db.add(override)
    requests = db.scalars(select(OverrideRequest).where(OverrideRequest.finding_id == finding.id, OverrideRequest.status == "PENDING")).all()
    for item in requests:
        item.status = "APPROVED"
    audit(db, case_id, "staff", user.id, "finding.overridden", {"finding_id": finding.id, "code": finding.code, "reason": payload.reason, "role": user.role})
    db.commit()
    return {"id": override.id, "finding_id": override.finding_id, "reason": override.reason, "actor_role": override.actor_role}


@app.post("/api/v1/clinic/cases/{case_id}/review")
def review_case(case_id: str, payload: ReviewAction, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
    case = db.scalar(case_query().where(Case.id == case_id, Case.clinic_id == user.clinic_id))
    if not case:
        raise HTTPException(404, "Case not found")
    if payload.action == "request_information":
        if case.status not in {"PROCESSING", "READY_FOR_REVIEW"}:
            raise HTTPException(409, "Information can only be requested from an active review")
        case.status = "NEEDS_ACTION"
        rate_limit(db, "notification", case.id, 3, 3600)
        notify(case.patient_email, f"Action needed for {case.reference}", payload.reason)
    elif payload.action == "approve":
        if payload.override_failures:
            raise HTTPException(422, "Inline failure overrides are not supported; use the manager override action")
        if case.status != "READY_FOR_REVIEW":
            raise HTTPException(409, "Case is not ready for a decision")
        if any(document.status in {"QUEUED", "PROCESSING"} or document.scan_status != "CLEAN" for document in case.documents):
            raise HTTPException(409, "All documents must finish scanning and processing before approval")
        evaluation = latest_evaluation(db, case.id)
        input_hash = current_input_hash(db, case)
        if not evaluation or evaluation.stale or evaluation.input_hash != input_hash:
            evaluation = evaluate_case(db, case)
            db.flush()
        findings = db.scalars(select(RuleFinding).where(RuleFinding.evaluation_id == evaluation.id)).all()
        overridden = {item.finding_id for item in db.scalars(select(FindingOverride).where(FindingOverride.case_id == case.id)).all()}
        unresolved = [item for item in findings if item.status != "PASS" and item.id not in overridden]
        if unresolved:
            raise HTTPException(409, {"message": "Resolve or request a manager override for every non-passing finding", "finding_ids": [item.id for item in unresolved]})
        case.status = "APPROVED_FOR_CHECK_IN"
        update_queue(case, "PROCEED_TO_REGISTRATION", "Registration Counter 2")
        db.add(ReviewDecision(case_id=case.id, evaluation_id=evaluation.id, decision="APPROVED_FOR_CHECK_IN", reason=payload.reason, actor_user_id=user.id))
        notify(case.patient_email, f"Ready for on-site check-in: {case.reference}", "Bring your original documents and identity/e-card for on-site checks. Administrative readiness is not a coverage guarantee.")
    else:
        if "CANCELLED" not in TRANSITIONS.get(case.status, set()):
            raise HTTPException(409, "Case cannot be cancelled")
        case.status = "CANCELLED"
    audit(db, case.id, "staff", user.id, f"review.{payload.action}", {"reason": payload.reason, "override_failures": payload.override_failures})
    db.commit()
    return serialize_case(case, db=db)


@app.post("/api/v1/clinic/cases/{case_id}/check-in")
def check_in(case_id: str, payload: CheckInRequest, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
    if settings.clinicpass_v2_enabled:
        raise HTTPException(410, "Use individual on-site attestation records for ClinicPass V2")
    case = db.scalar(case_query().where(Case.id == case_id, Case.clinic_id == user.clinic_id))
    if not case:
        raise HTTPException(404, "Case not found")
    if case.status != "APPROVED_FOR_CHECK_IN":
        raise HTTPException(409, "Case is not approved for check-in")
    if not all(payload.model_dump().values()):
        raise HTTPException(422, "All checks must be completed in person")
    case.check_in_confirmations = payload.model_dump()
    transition(case, "CHECKED_IN")
    update_queue(case, "CALLED_TO_ROOM", "Consultation Room 3")
    audit(db, case.id, "staff", user.id, "case.checked_in", payload.model_dump())
    db.commit()
    return serialize_case(case)


@app.post("/api/v1/clinic/cases/{case_id}/check-in/attestations", status_code=201)
def record_attestation(
    case_id: str,
    payload: AttestationCreate,
    user: User = Depends(current_staff),
    db: Session = Depends(get_db),
) -> dict:
    case = db.scalar(case_query().where(Case.id == case_id, Case.clinic_id == user.clinic_id))
    if not case:
        raise HTTPException(404, "Case not found")
    if case.status != "APPROVED_FOR_CHECK_IN":
        raise HTTPException(409, "Case is not approved for check-in")
    existing = db.scalar(select(OnSiteAttestation).where(
        OnSiteAttestation.case_id == case.id,
        OnSiteAttestation.attestation_type == payload.attestation_type,
    ))
    if existing:
        raise HTTPException(409, "This on-site check has already been attested")
    attestation = OnSiteAttestation(case_id=case.id, attestation_type=payload.attestation_type, actor_user_id=user.id)
    db.add(attestation)
    db.flush()
    count = db.scalar(select(func.count(OnSiteAttestation.id)).where(OnSiteAttestation.case_id == case.id)) or 0
    completed = count == 3
    if completed:
        case.check_in_confirmations = {
            "identity_checked_on_site": True,
            "ecard_checked_on_site": True,
            "originals_checked_on_site": True,
        }
        transition(case, "CHECKED_IN")
        update_queue(case, "CALLED_TO_ROOM", "Consultation Room 3")
    audit(db, case.id, "staff", user.id, "check_in.attested", {"attestation_type": payload.attestation_type, "check_in_completed": completed})
    db.commit()
    return {"attestation": {"id": attestation.id, "type": attestation.attestation_type, "attested_at": attestation.attested_at.isoformat()}, "case": serialize_case(case, db=db)}


def canonical_export_payload(db: Session, case: Case, idempotency_key: str) -> dict:
    profile = db.scalar(select(PatientProfile).where(PatientProfile.case_id == case.id))
    questionnaires = db.scalars(select(QuestionnaireSubmission).where(QuestionnaireSubmission.case_id == case.id)).all()
    evaluation = latest_evaluation(db, case.id)
    assertions = db.scalars(select(FieldAssertion).where(FieldAssertion.case_id == case.id)).all()
    corrections = db.scalars(select(StaffCorrection).where(StaffCorrection.case_id == case.id).order_by(StaffCorrection.created_at)).all()
    overrides = db.scalars(select(FindingOverride).where(FindingOverride.case_id == case.id)).all()
    decisions = db.scalars(select(ReviewDecision).where(ReviewDecision.case_id == case.id).order_by(ReviewDecision.created_at)).all()
    attestations = db.scalars(select(OnSiteAttestation).where(OnSiteAttestation.case_id == case.id)).all()
    return {
        "schema_version": "2.0.0",
        "idempotency_key": idempotency_key,
        "case": {"id": case.id, "reference": case.reference, "status": case.status, "clinic_id": case.clinic_id},
        "patient": serialize_profile(profile) or {"full_name": case.patient_name, "masked_identity": f"••••{case.id_last4}", "email": case.patient_email},
        "visit": {"appointment_type": case.appointment_type, "appointment_date": case.appointment_date.isoformat() if case.appointment_date else None, "visit_reason": case.visit_reason},
        "questionnaire": [
            {"type": item.questionnaire_type, "definition_version": item.definition_version, "responses": item.responses, "consents": item.consents, "signature_metadata": item.signature_metadata, "confirmed_prefill_fields": item.confirmed_prefill_fields}
            for item in questionnaires
        ],
        "eligibility": serialize_evaluation(db, evaluation) if evaluation else None,
        "requested_services": case.requested_services or [],
        "documents": [
            {
                "id": document.id,
                "category": document.category,
                "filename": document.filename,
                "sha256": document.sha256,
                "page_count": document.page_count,
                "assertions": [serialize_assertion(item, next((correction for correction in reversed(corrections) if correction.assertion_id == item.id), None)) for item in assertions if item.document_id == document.id],
            }
            for document in case.documents
        ],
        "staff_review": [{"decision": item.decision, "reason": item.reason, "actor_user_id": item.actor_user_id, "created_at": item.created_at.isoformat()} for item in decisions],
        "corrections": [{"assertion_id": item.assertion_id, "field_name": item.field_name, "original_value": item.original_value, "corrected_value": item.corrected_value, "reason": item.reason, "actor_user_id": item.actor_user_id, "created_at": item.created_at.isoformat()} for item in corrections],
        "overrides": [{"finding_id": item.finding_id, "reason": item.reason, "actor_user_id": item.actor_user_id, "actor_role": item.actor_role, "created_at": item.created_at.isoformat()} for item in overrides],
        "on_site_checks": [{"type": item.attestation_type, "actor_user_id": item.actor_user_id, "attested_at": item.attested_at.isoformat()} for item in attestations],
    }


@app.post("/api/v1/clinic/cases/{case_id}/export")
def export_case(
    case_id: str,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(current_staff),
    db: Session = Depends(get_db),
) -> dict:
    case = db.scalar(case_query().where(Case.id == case_id, Case.clinic_id == user.clinic_id))
    if not case or case.status not in {"CHECKED_IN", "EXPORTED"}:
        raise HTTPException(409, "Only checked-in cases can be exported")
    existing_export = db.scalar(select(IntegrationExport).where(IntegrationExport.case_id == case.id, IntegrationExport.idempotency_key == idempotency_key))
    if case.status == "EXPORTED":
        if existing_export and existing_export.status == "ACCEPTED":
            return {"case": serialize_case(case, db=db), "export": existing_export.response_payload, "idempotent_replay": True}
        raise HTTPException(409, "Case was exported with a different idempotency key")
    payload = canonical_export_payload(db, case, idempotency_key)
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    request_hash = hashlib.sha256(payload_json.encode()).hexdigest()
    export = existing_export
    if export:
        if export.request_hash != request_hash:
            raise HTTPException(409, "Idempotency key was already used for a different export payload")
        if export.status == "ACCEPTED":
            return {"case": serialize_case(case, db=db), "export": export.response_payload, "idempotent_replay": True}
    else:
        export = IntegrationExport(
            case_id=case.id,
            schema_version="2.0.0",
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            request_payload=payload,
            correlation_id=secrets.token_hex(16),
        )
        db.add(export)
        db.flush()
    export.attempts += 1
    try:
        with httpx.Client(timeout=5) as client:
            response = client.post(
                settings.clinic_assist_url,
                headers={
                    "X-Clinic-Assist-Key": settings.clinic_assist_secret,
                    "Idempotency-Key": idempotency_key,
                    "X-Correlation-ID": export.correlation_id,
                    "Content-Type": "application/json",
                },
                content=payload_json,
            )
            response.raise_for_status()
            result = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        export.status = "FAILED"
        export.response_payload = {"error_type": type(exc).__name__}
        audit(db, case.id, "staff", user.id, "case.export_failed", {"export_id": export.id, "attempt": export.attempts, "error_type": type(exc).__name__})
        db.commit()
        raise HTTPException(502, "Clinic Assist export was rejected or unavailable; the case remains checked in") from exc
    export.status = "ACCEPTED"
    export.response_payload = result
    transition(case, "EXPORTED")
    audit(db, case.id, "staff", user.id, "case.exported", {"export_id": export.id, "reference": result.get("reference"), "attempts": export.attempts})
    db.commit()
    return {"case": serialize_case(case, db=db), "export": result, "idempotent_replay": False}


@app.get("/api/v1/admin/metrics")
def metrics(_: User = Depends(manager_only), db: Session = Depends(get_db)) -> dict:
    rows = db.execute(select(Case.status, func.count(Case.id)).group_by(Case.status)).all()
    return {"total": sum(count for _, count in rows), "by_status": {status: count for status, count in rows}, "disclaimer": "Synthetic operational metrics only."}


@app.get("/api/v1/admin/reference-data")
def reference_data(_: User = Depends(manager_only), db: Session = Depends(get_db)) -> list[dict]:
    return [{"id": row.id, "kind": row.kind, "code": row.code, "label": row.label, "active": row.active} for row in db.scalars(select(ReferenceData).order_by(ReferenceData.kind, ReferenceData.code))]


REFERENCE_MODELS = {
    "organisations": PayerOrganisation,
    "contracts": EligibilityContract,
    "packages": PackageVersion,
    "procedures": Procedure,
    "package-procedures": PackageProcedure,
    "panel-rules": ClinicPanelRule,
    "billing-rules": BillingRule,
}


@app.get("/api/v1/admin/reference-data/{entity}")
def get_versioned_reference_data(entity: str, _: User = Depends(manager_only), db: Session = Depends(get_db)) -> list[dict]:
    if entity == "releases":
        return [
            {"id": row.id, "version": row.version, "description": row.description, "active": row.active, "activated_at": row.activated_at.isoformat() if row.activated_at else None}
            for row in db.scalars(select(ReferenceDataRelease).order_by(ReferenceDataRelease.created_at.desc())).all()
        ]
    model = REFERENCE_MODELS.get(entity)
    if not model:
        raise HTTPException(404, "Reference-data entity not found")
    return [
        {column.name: getattr(row, column.name) for column in model.__table__.columns}
        for row in db.scalars(select(model)).all()
    ]


@app.post("/api/v1/admin/reference-data/{entity}", status_code=201)
def create_versioned_reference_data(
    entity: str,
    payload: dict,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
) -> dict:
    if entity == "releases":
        if payload.get("active"):
            raise HTTPException(422, "Create a draft release first; activation is a separate audited operation")
        release = ReferenceDataRelease(version=str(payload.get("version", "")).strip(), description=str(payload.get("description", "")).strip(), active=False)
        if not release.version or not release.description:
            raise HTTPException(422, "Version and description are required")
        db.add(release)
        db.flush()
        audit(db, None, "staff", user.id, "reference_release.created", {"release_id": release.id, "version": release.version})
        db.commit()
        return {"id": release.id, "version": release.version, "active": False}
    model = REFERENCE_MODELS.get(entity)
    if not model:
        raise HTTPException(404, "Reference-data entity not found")
    release_id = payload.get("release_id")
    draft_release = db.get(ReferenceDataRelease, release_id) if release_id else None
    if not draft_release:
        raise HTTPException(422, "A valid draft release_id is required")
    if draft_release.active:
        raise HTTPException(409, "Active reference-data releases are immutable")
    allowed = {column.name for column in model.__table__.columns} - {"id"}
    values = {key: value for key, value in payload.items() if key in allowed}
    try:
        row = model(**values)
        db.add(row)
        db.flush()
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, "Invalid reference-data record") from exc
    audit(db, None, "staff", user.id, "reference_record.created", {"entity": entity, "record_id": getattr(row, "id"), "release_id": draft_release.id})
    db.commit()
    return {column.name: getattr(row, column.name) for column in model.__table__.columns}


@app.post("/api/v1/admin/reference-data/releases/{release_id}/activate")
def activate_reference_release(release_id: str, user: User = Depends(manager_only), db: Session = Depends(get_db)) -> dict:
    release = db.get(ReferenceDataRelease, release_id)
    if not release:
        raise HTTPException(404, "Reference-data release not found")
    for item in db.scalars(select(ReferenceDataRelease).where(ReferenceDataRelease.active.is_(True))).all():
        item.active = False
    release.active = True
    release.activated_at = datetime.now(timezone.utc)
    for case_id in db.scalars(select(Case.id)).all():
        invalidate_evaluations(db, case_id)
    audit(db, None, "staff", user.id, "reference_release.activated", {"release_id": release.id, "version": release.version})
    db.commit()
    return {"id": release.id, "version": release.version, "active": True}


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile)))
    return ordered[index]


@app.get("/api/v1/admin/evaluation-metrics")
def evaluation_metrics(_: User = Depends(manager_only), db: Session = Depends(get_db)) -> dict:
    evaluations = db.scalars(select(EligibilityEvaluation)).all()
    operational = db.scalars(select(ProcessingMetric)).all()
    latest_benchmark = db.scalar(select(BenchmarkRun).order_by(BenchmarkRun.created_at.desc()).limit(1))
    durations = [row.value for row in operational if row.name == "processing_latency_seconds"]
    return {
        "evaluation_count": len(evaluations),
        "outcomes": {outcome: sum(1 for item in evaluations if item.outcome == outcome) for outcome in {item.outcome for item in evaluations}},
        "processing_latency_seconds": {"p50": _percentile(durations, 0.50), "p95": _percentile(durations, 0.95)},
        "latest_benchmark": latest_benchmark.metrics if latest_benchmark else None,
        "targets_are_not_claims": latest_benchmark is None,
        "disclaimer": "Synthetic, privacy-safe administrative workflow metrics only.",
    }


@app.get("/api/v1/admin/audit")
def audit_log(case_id: str | None = None, _: User = Depends(manager_only), db: Session = Depends(get_db)) -> list[dict]:
    query = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(250)
    if case_id:
        query = query.where(AuditEvent.case_id == case_id)
    rows = db.scalars(query).all()
    integrity_rows = list(db.scalars(select(AuditEvent).order_by(AuditEvent.created_at, AuditEvent.id)).all())
    return [{"id": row.id, "case_id": row.case_id, "actor_type": row.actor_type, "actor_id": row.actor_id, "action": row.action, "details": row.details, "created_at": row.created_at.isoformat(), "integrity_digest": row.integrity_digest, "chain_verified": verify_audit_chain(integrity_rows)} for row in rows]


# A deliberately narrow facade for a future Copilot Studio agent. These endpoints
# reuse the same authorization and domain service paths as the Web UI.
@app.get("/api/v1/copilot/cases")
def copilot_search_cases(search: str | None = None, status: str | None = None, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> list[dict]:
    return list_cases(status, search, user, db)


@app.get("/api/v1/copilot/cases/{case_id}/summary")
def copilot_case_summary(case_id: str, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
    case = get_staff_case(case_id, user, db)
    return {
        "reference": case["reference"],
        "status": case["status"],
        "visit_reason": case["visit_reason"],
        "document_requirement": case["document_requirement"],
        "identity_source": case["identity_source"],
        "queue_number": case["queue_number"],
        "queue_status": case["queue_status"],
        "room_assignment": case["room_assignment"],
        "readiness_checks": case["rules"],
        "eligibility": case.get("evaluation"),
        "ai_provider": case["ai_provider"],
        "disclaimer": "Administrative readiness only; verify identity and originals on site.",
    }


@app.get("/api/v1/copilot/cases/{case_id}/exceptions")
def copilot_exceptions(case_id: str, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
    case = get_staff_case(case_id, user, db)
    return {"exceptions": [rule for rule in case["rules"] if rule["status"] != "PASS"]}


@app.get("/api/v1/copilot/cases/{case_id}/evidence/{document_id}")
def copilot_evidence(case_id: str, document_id: str, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
    case = get_staff_case(case_id, user, db)
    document = next((doc for doc in case["documents"] if doc["id"] == document_id), None)
    if not document:
        raise HTTPException(404, "Evidence not found")
    return {"document_id": document_id, "evidence": document["evidence"], "field_assertions": [item for item in case.get("assertions", []) if item["document_id"] == document_id]}


@app.get("/api/v1/copilot/cases/{case_id}/evaluation")
def copilot_evaluation(case_id: str, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
    return get_case_evaluation(case_id, user, db)


@app.get("/api/v1/copilot/cases/{case_id}/findings")
def copilot_explain_findings(case_id: str, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
    evaluation = get_case_evaluation(case_id, user, db)
    return {"outcome": evaluation["outcome"], "findings": evaluation["findings"], "disclaimer": "Provisional administrative eligibility only."}


@app.get("/api/v1/copilot/cases/{case_id}/export-status")
def copilot_export_status(case_id: str, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
    case = db.scalar(select(Case).where(Case.id == case_id, Case.clinic_id == user.clinic_id))
    if not case:
        raise HTTPException(404, "Case not found")
    item = db.scalar(select(IntegrationExport).where(IntegrationExport.case_id == case_id).order_by(IntegrationExport.created_at.desc()).limit(1))
    return {"case_status": case.status, "export": {"status": item.status, "attempts": item.attempts, "correlation_id": item.correlation_id, "response": item.response_payload} if item else None}


@app.post("/api/v1/copilot/cases/{case_id}/patient-request")
def copilot_patient_request(case_id: str, payload: ReviewAction, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
    if payload.action != "request_information":
        raise HTTPException(422, "This action only submits patient information requests")
    return review_case(case_id, payload, user, db)


@app.post("/api/v1/copilot/cases/{case_id}/patient-request/draft")
def copilot_draft_patient_request(case_id: str, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
    case = get_staff_case(case_id, user, db)
    missing = [rule["label"] for rule in case["rules"] if rule["status"] != "PASS"]
    return {
        "draft": f"We need more information for {case['reference']}: {', '.join(missing) or 'please confirm the submitted details'}. Reply using your secure ClinicPass link.",
        "requires_staff_confirmation": True,
    }


@app.post("/api/v1/copilot/cases/{case_id}/correction/draft")
def copilot_draft_correction(case_id: str, payload: CorrectionPatch, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
    get_staff_case(case_id, user, db)
    return {"draft": f"Correct the selected extracted field because: {payload.reason}", "proposed_value": payload.corrected_value, "requires_staff_confirmation": True}


@app.patch("/api/v1/copilot/cases/{case_id}/assertions/{assertion_id}")
def copilot_record_correction(case_id: str, assertion_id: str, payload: CorrectionPatch, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
    return correct_assertion(case_id, assertion_id, payload, user, db)


@app.post("/api/v1/copilot/cases/{case_id}/override-requests")
def copilot_request_override(case_id: str, payload: OverrideRequestCreate, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
    return request_override(case_id, payload, user, db)


@app.post("/api/v1/copilot/cases/{case_id}/export")
def copilot_retry_export(case_id: str, idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100), user: User = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
    return export_case(case_id, idempotency_key, user, db)


@app.post("/api/v1/copilot/cases/{case_id}/decision")
def copilot_decision(case_id: str, payload: ReviewAction, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
    return review_case(case_id, payload, user, db)
