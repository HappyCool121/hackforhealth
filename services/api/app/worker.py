import time
from sqlalchemy import select
from .db import Base, SessionLocal, engine
from .models import Case, Document
from .processing import process_document


def run() -> None:
    Base.metadata.create_all(engine)
    while True:
        with SessionLocal() as db:
            document = db.scalar(
                select(Document)
                .join(Case, Case.id == Document.case_id)
                .where(Document.status == "QUEUED", Case.status.in_({"DRAFT", "NEEDS_ACTION", "PROCESSING"}))
                .order_by(Document.created_at)
                .with_for_update(skip_locked=True)
            )
            if document:
                process_document(db, document)
                continue
        time.sleep(2)


if __name__ == "__main__":
    run()
