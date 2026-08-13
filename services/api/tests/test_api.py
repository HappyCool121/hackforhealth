from io import BytesIO

import fitz
import pytest
from PIL import Image
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Document


def pdf_bytes(text: str = "SYNTHETIC DEMO DOCUMENT") -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    content = document.tobytes()
    document.close()
    return content


def image_bytes() -> bytes:
    image = Image.new("RGB", (500, 240), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_patient_to_staff_thin_slice(client):
    created = client.post("/api/v1/patient/cases", json={
        "patient_name": "Synthetic Jamie Tan",
        "patient_email": "jamie@example.test",
        "id_last4": "123A",
        "appointment_type": "walk-in",
    })
    assert created.status_code == 201
    case = created.json()
    assert case["status"] == "DRAFT"
    assert case["document_requirement"] == "yes"
    assert case["visit_reason"] == "other_unsure"

    upload = client.post(
        f"/api/v1/patient/cases/{case['id']}/documents",
        files={"file": ("voucher.pdf", pdf_bytes("SCREENING VOUCHER"), "application/pdf")},
    )
    assert upload.status_code == 201
    assert upload.json()["expected_category"] == "unknown"
    assert upload.json()["page_count"] == 1
    submitted = client.post(f"/api/v1/patient/cases/{case['id']}/submit")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "PROCESSING"
    assert submitted.json()["queue_number"].startswith("Q")
    assert submitted.json()["queue_status"] == "WAITING_FOR_REVIEW"
    assert submitted.json()["room_assignment"] == "Waiting area"

    login = client.post("/api/v1/auth/login", json={"email": "assistant@clinicpass.test", "password": "DemoAssistant1!"})
    assert login.status_code == 200
    queue = client.get("/api/v1/clinic/cases")
    assert any(item["id"] == case["id"] for item in queue.json())


def test_manager_boundary(client):
    client.post("/api/v1/auth/login", json={"email": "assistant@clinicpass.test", "password": "DemoAssistant1!"})
    assert client.get("/api/v1/admin/metrics").status_code == 403
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"email": "manager@clinicpass.test", "password": "DemoManager1!"})
    assert client.get("/api/v1/admin/metrics").status_code == 200


def test_patient_access_link_rotates_after_first_use(client):
    created = client.post("/api/v1/patient/cases", json={
        "patient_name": "Synthetic Link Test",
        "patient_email": "link@example.test",
        "id_last4": "555Z",
        "appointment_type": "walk-in",
    }).json()
    token = created["access_url"].split("token=", 1)[1]
    client.cookies.clear()
    first = client.post(f"/api/v1/patient/cases/{created['id']}/access?token={token}")
    assert first.status_code == 200
    client.cookies.clear()
    second = client.post(f"/api/v1/patient/cases/{created['id']}/access?token={token}")
    assert second.status_code == 404


@pytest.mark.parametrize("document_requirement", ["no", "unsure"])
def test_documentless_declaration_routes_to_staff_review(client, document_requirement):
    created = client.post("/api/v1/patient/cases", json={
        "patient_name": "Synthetic No Document",
        "patient_email": "nodoc@example.test",
        "id_last4": "777Q",
        "appointment_type": "walk-in",
        "visit_reason": "gp_consultation",
        "document_requirement": document_requirement,
        "identity_source": "singpass_demo",
    })
    assert created.status_code == 201
    submitted = client.post(f"/api/v1/patient/cases/{created.json()['id']}/submit")
    assert submitted.status_code == 200
    result = submitted.json()
    assert result["status"] == "READY_FOR_REVIEW"
    assert next(rule for rule in result["rules"] if rule["code"] == "supporting")["status"] == "REVIEW"
    assert result["identity_source"] == "singpass_demo"
    assert result["queue_number"].startswith("Q")


def test_queue_and_room_updates_follow_staff_actions(client):
    created = client.post("/api/v1/patient/cases", json={
        "patient_name": "Synthetic Queue Patient",
        "patient_email": "queue@example.test",
        "id_last4": "909Q",
        "appointment_type": "walk-in",
        "document_requirement": "no",
    }).json()
    submitted = client.post(f"/api/v1/patient/cases/{created['id']}/submit").json()
    queue_number = submitted["queue_number"]

    client.post("/api/v1/auth/login", json={
        "email": "assistant@clinicpass.test",
        "password": "DemoAssistant1!",
    })
    approved = client.post(f"/api/v1/clinic/cases/{created['id']}/review", json={
        "action": "approve",
        "reason": "Synthetic queue demo approved",
        "override_failures": False,
    })
    assert approved.status_code == 200
    assert approved.json()["queue_number"] == queue_number
    assert approved.json()["queue_status"] == "PROCEED_TO_REGISTRATION"
    assert approved.json()["room_assignment"] == "Registration Counter 2"

    checked_in = client.post(f"/api/v1/clinic/cases/{created['id']}/check-in", json={
        "identity_checked_on_site": True,
        "ecard_checked_on_site": True,
        "originals_checked_on_site": True,
    })
    assert checked_in.status_code == 200
    assert checked_in.json()["queue_status"] == "CALLED_TO_ROOM"
    assert checked_in.json()["room_assignment"] == "Consultation Room 3"


def test_declared_required_document_cannot_be_skipped(client):
    created = client.post("/api/v1/patient/cases", json={
        "patient_name": "Synthetic Required Document",
        "patient_email": "required@example.test",
        "id_last4": "123A",
        "appointment_type": "walk-in",
        "visit_reason": "corporate_insurer_screening",
        "document_requirement": "yes",
    }).json()
    submitted = client.post(f"/api/v1/patient/cases/{created['id']}/submit")
    assert submitted.status_code == 409
    assert "indicated documents are needed" in submitted.json()["detail"]


@pytest.mark.parametrize("visit_reason", [
    "gp_consultation",
    "corporate_insurer_screening",
    "occupational_health_screening",
    "employer_insurer_medical_exam",
    "healthier_sg_periodic_checkup",
    "other_unsure",
])
def test_all_visit_reasons_are_accepted(client, visit_reason):
    created = client.post("/api/v1/patient/cases", json={
        "patient_name": "Synthetic Visit Reason",
        "patient_email": "reason@example.test",
        "id_last4": "111A",
        "appointment_type": "walk-in",
        "visit_reason": visit_reason,
        "document_requirement": "unsure",
    })
    assert created.status_code == 201
    assert created.json()["visit_reason"] == visit_reason


def test_generic_image_upload_remove_and_retry(client):
    case = client.post("/api/v1/patient/cases", json={
        "patient_name": "Synthetic Upload Test",
        "patient_email": "upload@example.test",
        "id_last4": "222B",
        "appointment_type": "walk-in",
    }).json()
    first = client.post(
        f"/api/v1/patient/cases/{case['id']}/documents",
        files={"file": ("camera.png", image_bytes(), "image/png")},
    )
    assert first.status_code == 201
    document_id = first.json()["id"]
    with SessionLocal() as db:
        document = db.scalar(select(Document).where(Document.id == document_id))
        assert document is not None
        document.status = "ERROR"
        document.error = "Synthetic failure"
        db.commit()
    retried = client.post(f"/api/v1/patient/cases/{case['id']}/documents/{document_id}/retry")
    assert retried.status_code == 200
    assert retried.json()["status"] == "QUEUED"
    removed = client.delete(f"/api/v1/patient/cases/{case['id']}/documents/{document_id}")
    assert removed.status_code == 204


def test_upload_validation_rejects_unsupported_large_and_password_pdf(client):
    case = client.post("/api/v1/patient/cases", json={
        "patient_name": "Synthetic Validation",
        "patient_email": "validation@example.test",
        "id_last4": "333C",
        "appointment_type": "walk-in",
    }).json()
    endpoint = f"/api/v1/patient/cases/{case['id']}/documents"
    unsupported = client.post(endpoint, files={"file": ("notes.txt", b"hello", "text/plain")})
    assert unsupported.status_code == 415
    oversized = client.post(
        endpoint,
        files={"file": ("large.png", b"0" * (10 * 1024 * 1024 + 1), "image/png")},
    )
    assert oversized.status_code == 413

    protected = fitz.open()
    protected.new_page().insert_text((72, 72), "SYNTHETIC PROTECTED PDF")
    protected_bytes = protected.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner-demo",
        user_pw="patient-demo",
    )
    protected.close()
    encrypted = client.post(endpoint, files={"file": ("protected.pdf", protected_bytes, "application/pdf")})
    assert encrypted.status_code == 422
    assert "Password-protected" in encrypted.json()["detail"]
