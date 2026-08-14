from __future__ import annotations
from pathlib import Path
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from .ai import get_provider
from .config import get_settings
from .eligibility import evaluate_case
from .models import Case, Document, FieldAssertion
from .ocr import extract_evidence, prepare_document_images
from .rules import evaluate, readiness_status
from .security import append_audit


def finalize_case_if_ready(case: Case, db: Session | None = None) -> None:
    if case.status != "PROCESSING":
        return
    if any(item.status in {"QUEUED", "PROCESSING"} for item in case.documents):
        return
    if get_settings().clinicpass_v2_enabled and db is not None:
        evaluation = evaluate_case(db, case)
        case.status = "NEEDS_ACTION" if evaluation.outcome == "BLOCKED" else "READY_FOR_REVIEW"
    else:
        case.rules = evaluate(case)
        case.status = readiness_status(case.rules)


def materialize_assertions(db: Session, case: Case, document: Document, result) -> None:
    db.execute(delete(FieldAssertion).where(FieldAssertion.document_id == document.id))
    evidence_index = {item.evidence_id: item for item in result.evidence}
    for field_name, value in result.fields.items():
        evidence_ids = result.field_evidence.get(field_name, [])
        cited = [evidence_index[item] for item in evidence_ids if item in evidence_index]
        status = "SUPPORTED" if value is not None and cited else "UNSUPPORTED"
        existing = db.scalars(select(FieldAssertion).where(
            FieldAssertion.case_id == case.id,
            FieldAssertion.field_name == field_name,
            FieldAssertion.normalized_value.is_not(None),
        )).all()
        if value is not None and any((row.normalized_value or "").strip().casefold() != str(value).strip().casefold() for row in existing):
            status = "CONFLICTING"
            for row in existing:
                row.support_status = "CONFLICTING"
        db.add(FieldAssertion(
            case_id=case.id,
            document_id=document.id,
            field_name=field_name,
            raw_value=None if value is None else str(value),
            normalized_value=None if value is None else str(value).strip(),
            page=cited[0].page if cited else None,
            evidence_ids=evidence_ids,
            bounding_boxes=[item.bbox for item in cited if item.bbox],
            extraction_provider=document.processing_provider or "unknown",
            support_status=status,
            validation_errors=[] if status == "SUPPORTED" else (["No field-level citation"] if value is not None else ["Field not found"]),
        ))
    db.flush()


def materialize_document(document: Document) -> str:
    """Restore a queued upload after a free Render instance loses its filesystem."""
    path = Path(document.storage_path)
    if path.exists():
        return str(path)
    if document.content is None:
        raise FileNotFoundError("Uploaded document is no longer available")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(document.content)
    return str(path)


def process_document(db: Session, document: Document) -> None:
    settings = get_settings()
    document.status = "PROCESSING"
    document.processing_provider = settings.ai_provider
    db.commit()
    try:
        document_path = materialize_document(document)
        evidence, quality = extract_evidence(document_path)
        images = prepare_document_images(
            document_path,
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
            materialize_assertions(db, case, document, result)
            finalize_case_if_ready(case, db)
        append_audit(db, document.case_id, "system", settings.ai_provider, "document.processed", {"document_id": document.id, "category": document.category})
    except Exception as exc:
        document.status = "ERROR"
        document.error = f"{type(exc).__name__}: {exc}"[:1000]
        case = db.get(Case, document.case_id)
        if case:
            case.ai_provider = settings.ai_provider
            finalize_case_if_ready(case, db)
        append_audit(db, document.case_id, "system", "worker", "document.processing_failed", {"document_id": document.id, "error_type": type(exc).__name__})
    db.commit()
