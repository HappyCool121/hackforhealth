from __future__ import annotations
from sqlalchemy.orm import Session
from .ai import get_provider
from .config import get_settings
from .models import AuditEvent, Case, Document
from .ocr import extract_evidence, prepare_document_images
from .rules import evaluate, readiness_status


def finalize_case_if_ready(case: Case) -> None:
    if case.status != "PROCESSING":
        return
    if any(item.status in {"QUEUED", "PROCESSING"} for item in case.documents):
        return
    case.rules = evaluate(case)
    case.status = readiness_status(case.rules)


def process_document(db: Session, document: Document) -> None:
    settings = get_settings()
    document.status = "PROCESSING"
    document.processing_provider = settings.ai_provider
    db.commit()
    try:
        evidence, quality = extract_evidence(document.storage_path)
        images = prepare_document_images(
            document.storage_path,
            max_pages=settings.max_document_pages,
            max_dimension=settings.max_image_dimension,
            jpeg_quality=settings.image_jpeg_quality,
        )
        result = get_provider().extract(evidence, document.expected_category, images)
        document.category = result.category
        document.extracted_data = result.fields
        document.evidence = [item.model_dump() for item in result.evidence]
        document.quality_warnings = quality + result.warnings
        document.status = "COMPLETE"
        case = db.get(Case, document.case_id)
        if case:
            case.ai_provider = settings.ai_provider
            finalize_case_if_ready(case)
        db.add(AuditEvent(case_id=document.case_id, actor_type="system", actor_id=settings.ai_provider, action="document.processed", details={"document_id": document.id, "category": document.category}))
    except Exception as exc:
        document.status = "ERROR"
        document.error = f"{type(exc).__name__}: {exc}"[:1000]
        case = db.get(Case, document.case_id)
        if case:
            case.ai_provider = settings.ai_provider
            finalize_case_if_ready(case)
        db.add(AuditEvent(case_id=document.case_id, actor_type="system", actor_id="worker", action="document.processing_failed", details={"document_id": document.id, "error_type": type(exc).__name__}))
    db.commit()
