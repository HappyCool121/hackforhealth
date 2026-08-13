from __future__ import annotations
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import secrets
import smtplib
from email.message import EmailMessage
import httpx
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, Depends, FastAPI, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .auth import create_session, current_staff, hash_token, manager_only, ph
from .config import get_settings
from .db import Base, SessionLocal, engine, get_db
from .models import AuditEvent, Case, Document, ReferenceData, StaffSession, User
from .ocr import inspect_upload
from .processing import finalize_case_if_ready
from .schemas import CaseCreate, CasePatch, CheckInRequest, LoginRequest, ReviewAction


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
        ("assistant@clinicpass.test", "Clinic Assistant", "assistant", "DemoAssistant1!"),
        ("manager@clinicpass.test", "Clinic Manager", "manager", "DemoManager1!"),
    ]
    for email, name, role, password in users:
        if not db.scalar(select(User).where(User.email == email)):
            db.add(User(email=email, name=name, role=role, password_hash=ph.hash(password)))
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
    yield


app = FastAPI(
    title="ClinicPass API",
    version="0.1.0",
    description="Administrative pre-registration and eligibility-readiness API. Not for clinical decisions or coverage guarantees.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)


def audit(db: Session, case_id: str | None, actor_type: str, actor_id: str | None, action: str, details: dict | None = None) -> None:
    db.add(AuditEvent(case_id=case_id, actor_type=actor_type, actor_id=actor_id, action=action, details=details or {}))


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


def serialize_case(case: Case, detail: bool = True) -> dict:
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
    return result


def patient_case(db: Session, case_id: str, token: str | None) -> Case:
    case = db.scalar(case_query().where(Case.id == case_id))
    if not case or not token or not secrets.compare_digest(case.patient_token_hash, hash_token(token)):
        raise HTTPException(404, "Case not found")
    return case


def notify(email: str, subject: str, text: str) -> None:
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
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    try:
        valid = bool(user and ph.verify(user.password_hash, payload.password))
    except VerifyMismatchError:
        valid = False
    if not valid or not user or not user.active:
        raise HTTPException(401, "Invalid email or password")
    create_session(db, user, response)
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
        clinic_id=payload.clinic_id,
        patient_token_hash=hash_token(raw_token),
    )
    db.add(case)
    db.flush()
    audit(db, case.id, "patient", "self", "case.created")
    db.commit()
    response.set_cookie("cp_patient", raw_token, httponly=True, samesite="lax", secure=False, max_age=7 * 86400, path="/")
    result = serialize_case(case)
    result["access_url"] = f"{settings.public_base_url}/patient/case/{case.id}?token={raw_token}"
    return result


@app.post("/api/v1/patient/cases/{case_id}/access")
def access_case(case_id: str, response: Response, token: str = Query(), db: Session = Depends(get_db)) -> dict:
    case = patient_case(db, case_id, token)
    rotated_token = secrets.token_urlsafe(32)
    case.patient_token_hash = hash_token(rotated_token)
    response.set_cookie("cp_patient", rotated_token, httponly=True, samesite="lax", secure=False, max_age=7 * 86400, path="/")
    audit(db, case.id, "patient", "link", "case.accessed", {"token_rotated": True})
    db.commit()
    return serialize_case(case)


@app.get("/api/v1/patient/cases/{case_id}")
def get_patient_case(case_id: str, cp_patient: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> dict:
    return serialize_case(patient_case(db, case_id, cp_patient))


@app.patch("/api/v1/patient/cases/{case_id}")
def update_patient_case(case_id: str, payload: CasePatch, cp_patient: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> dict:
    case = patient_case(db, case_id, cp_patient)
    if case.status not in {"DRAFT", "NEEDS_ACTION"}:
        raise HTTPException(409, "Case details cannot be edited in the current state")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(case, key, value)
    audit(db, case.id, "patient", "self", "case.updated", {"fields": list(payload.model_dump(exclude_unset=True))})
    db.commit()
    return serialize_case(case)


@app.post("/api/v1/patient/cases/{case_id}/documents", status_code=201)
async def upload_document(
    case_id: str,
    category: str | None = Form(default=None),
    file: UploadFile = File(),
    cp_patient: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> dict:
    case = patient_case(db, case_id, cp_patient)
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
    )
    db.add(doc)
    if case.status == "NEEDS_ACTION":
        case.rules = []
    audit(
        db,
        case.id,
        "patient",
        "self",
        "document.uploaded",
        {"document_id": doc.id, "category_hint": expected_category, "page_count": page_count},
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
    cp_patient: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> dict:
    case = patient_case(db, case_id, cp_patient)
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
    transition(case, "SUBMITTED")
    issue_queue(case)
    transition(case, "PROCESSING")
    finalize_case_if_ready(case)
    audit(db, case.id, "patient", "self", "case.submitted")
    db.commit()
    notify(case.patient_email, f"ClinicPass {case.reference} submitted", "Your synthetic demo registration was submitted for administrative review.")
    return serialize_case(case)


@app.get("/api/v1/clinic/cases")
def list_cases(status: str | None = None, search: str | None = None, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> list[dict]:
    query = case_query().where(Case.clinic_id == user.clinic_id).order_by(Case.updated_at.desc())
    if status:
        query = query.where(Case.status == status)
    if search:
        query = query.where(Case.patient_name.ilike(f"%{search}%") | Case.reference.ilike(f"%{search}%"))
    return [serialize_case(case, detail=False) for case in db.scalars(query).all()]


@app.get("/api/v1/clinic/cases/{case_id}")
def get_staff_case(case_id: str, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
    case = db.scalar(case_query().where(Case.id == case_id, Case.clinic_id == user.clinic_id))
    if not case:
        raise HTTPException(404, "Case not found")
    audit(db, case.id, "staff", user.id, "case.viewed")
    db.commit()
    return serialize_case(case)


@app.post("/api/v1/clinic/cases/{case_id}/review")
def review_case(case_id: str, payload: ReviewAction, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
    case = db.scalar(case_query().where(Case.id == case_id, Case.clinic_id == user.clinic_id))
    if not case:
        raise HTTPException(404, "Case not found")
    if payload.action == "request_information":
        if case.status not in {"PROCESSING", "READY_FOR_REVIEW"}:
            raise HTTPException(409, "Information can only be requested from an active review")
        case.status = "NEEDS_ACTION"
        notify(case.patient_email, f"Action needed for {case.reference}", payload.reason)
    elif payload.action == "approve":
        if case.status not in {"READY_FOR_REVIEW", "NEEDS_ACTION"}:
            raise HTTPException(409, "Case is not ready for a decision")
        failing = [rule for rule in case.rules if rule["status"] == "FAIL"]
        if failing and not payload.override_failures:
            raise HTTPException(409, "Explicit override is required for failing checks")
        case.status = "APPROVED_FOR_CHECK_IN"
        update_queue(case, "PROCEED_TO_REGISTRATION", "Registration Counter 2")
        notify(case.patient_email, f"Ready for on-site check-in: {case.reference}", "Bring your original documents and identity/e-card for on-site checks. Administrative readiness is not a coverage guarantee.")
    else:
        if "CANCELLED" not in TRANSITIONS.get(case.status, set()):
            raise HTTPException(409, "Case cannot be cancelled")
        case.status = "CANCELLED"
    audit(db, case.id, "staff", user.id, f"review.{payload.action}", {"reason": payload.reason, "override_failures": payload.override_failures})
    db.commit()
    return serialize_case(case)


@app.post("/api/v1/clinic/cases/{case_id}/check-in")
def check_in(case_id: str, payload: CheckInRequest, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
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


@app.post("/api/v1/clinic/cases/{case_id}/export")
def export_case(case_id: str, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
    case = db.scalar(case_query().where(Case.id == case_id, Case.clinic_id == user.clinic_id))
    if not case or case.status != "CHECKED_IN":
        raise HTTPException(409, "Only checked-in cases can be exported")
    with httpx.Client(timeout=5) as client:
        response = client.post(settings.clinic_assist_url, json={"case_id": case.id, "reference": case.reference, "patient": {"name": case.patient_name, "id_last4": case.id_last4}, "checks": case.check_in_confirmations})
        response.raise_for_status()
        result = response.json()
    transition(case, "EXPORTED")
    audit(db, case.id, "staff", user.id, "case.exported", result)
    db.commit()
    return {"case": serialize_case(case), "export": result}


@app.get("/api/v1/admin/metrics")
def metrics(_: User = Depends(manager_only), db: Session = Depends(get_db)) -> dict:
    rows = db.execute(select(Case.status, func.count(Case.id)).group_by(Case.status)).all()
    return {"total": sum(count for _, count in rows), "by_status": {status: count for status, count in rows}, "disclaimer": "Synthetic operational metrics only."}


@app.get("/api/v1/admin/reference-data")
def reference_data(_: User = Depends(manager_only), db: Session = Depends(get_db)) -> list[dict]:
    return [{"id": row.id, "kind": row.kind, "code": row.code, "label": row.label, "active": row.active} for row in db.scalars(select(ReferenceData).order_by(ReferenceData.kind, ReferenceData.code))]


@app.get("/api/v1/admin/audit")
def audit_log(case_id: str | None = None, _: User = Depends(manager_only), db: Session = Depends(get_db)) -> list[dict]:
    query = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(250)
    if case_id:
        query = query.where(AuditEvent.case_id == case_id)
    return [{"id": row.id, "case_id": row.case_id, "actor_type": row.actor_type, "actor_id": row.actor_id, "action": row.action, "details": row.details, "created_at": row.created_at.isoformat()} for row in db.scalars(query)]


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
    return {"document_id": document_id, "evidence": document["evidence"]}


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


@app.post("/api/v1/copilot/cases/{case_id}/decision")
def copilot_decision(case_id: str, payload: ReviewAction, user: User = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
    return review_case(case_id, payload, user, db)
