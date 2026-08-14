from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import SessionLocal
from .models import Case, Document, PatientProfile, QuestionnaireSubmission
from .security import append_audit


TERMINAL_STATUSES = {"CANCELLED", "EXPORTED", "COMPLETED"}


def purge_expired_data(db: Session) -> int:
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.retention_days)
    cases = db.scalars(
        select(Case).where(Case.status.in_(TERMINAL_STATUSES), Case.updated_at < cutoff)
    ).all()
    for case in cases:
        documents = db.scalars(select(Document).where(Document.case_id == case.id)).all()
        for document in documents:
            document.content = None
            try:
                Path(document.storage_path).unlink(missing_ok=True)
            except OSError:
                pass
        profile = db.scalar(select(PatientProfile).where(PatientProfile.case_id == case.id))
        if profile:
            profile.identity_number_encrypted = None
            profile.phone = None
            profile.address = None
            profile.postal_code = None
            profile.pregnancy_details = {}
        db.execute(delete(QuestionnaireSubmission).where(QuestionnaireSubmission.case_id == case.id))
        append_audit(db, case.id, "system", "retention", "case.sensitive_data_purged", {"retention_days": settings.retention_days})
    db.commit()
    return len(cases)


def main() -> None:
    with SessionLocal() as db:
        count = purge_expired_data(db)
    print(f"Purged sensitive data for {count} expired synthetic cases")


if __name__ == "__main__":
    main()
