from __future__ import annotations

import json
from pathlib import Path

import httpx
from jsonschema import Draft202012Validator
import pytest
from sqlalchemy import select

import app.main as main_module
from app.db import SessionLocal
from app.eligibility import evaluate_case, serialize_evaluation
from app.models import Case, Document, FieldAssertion

from test_api import complete_v2_intake, image_bytes


BASE_FIELDS = {
    "patient_name": "Synthetic Jamie Tan",
    "id_last4": "123A",
    "issuer": "Northstar Corporate Benefits",
    "valid_to": "2027-12-31",
    "clinic_id": "clinic-central",
    "organization_code": "ORG-DEMO",
    "package_code": "PKG-SCREEN",
    "billing_arrangement": "direct",
    "payer": "Demo Health Fund",
}


def prepared_case(client, fields: dict[str, str] | None = None, requested_services: list[str] | None = None):
    created = client.post("/api/v1/patient/cases", json={
        "patient_name": "Synthetic Jamie Tan",
        "patient_email": "jamie@example.test",
        "id_last4": "123A",
        "appointment_type": "scheduled",
        "appointment_date": "2027-01-10",
        "visit_reason": "corporate_insurer_screening",
        "document_requirement": "yes",
        "requested_services": requested_services or ["BASIC_SCREEN"],
    }).json()
    complete_v2_intake(client, created)
    with SessionLocal() as db:
        case = db.scalar(select(Case).where(Case.id == created["id"]))
        assert case is not None
        document = Document(
            case_id=case.id,
            expected_category="medical_chit",
            category="medical_chit",
            filename="synthetic-medical-chit.pdf",
            media_type="application/pdf",
            page_count=1,
            sha256="a" * 64,
            storage_path="/tmp/synthetic-medical-chit.pdf",
            status="COMPLETE",
            scan_status="CLEAN",
            extracted_data=fields or BASE_FIELDS,
        )
        db.add(document)
        db.flush()
        assertion_ids = {}
        for field_name, value in (fields or BASE_FIELDS).items():
            assertion = FieldAssertion(
                case_id=case.id,
                document_id=document.id,
                field_name=field_name,
                raw_value=value,
                normalized_value=value,
                page=1,
                evidence_ids=[f"p1-{field_name}"],
                bounding_boxes=[[10, 10, 100, 30]],
                extraction_provider="fixture",
                support_status="SUPPORTED",
            )
            db.add(assertion)
            db.flush()
            assertion_ids[field_name] = assertion.id
        evaluation = evaluate_case(db, case)
        case.status = "NEEDS_ACTION" if evaluation.outcome == "BLOCKED" else "READY_FOR_REVIEW"
        db.commit()
        result = serialize_evaluation(db, evaluation)
    return created, result, assertion_ids


def test_clean_package_is_provisionally_eligible(client):
    _, evaluation, _ = prepared_case(client)
    assert evaluation["outcome"] == "PROVISIONALLY_ELIGIBLE"
    assert len(evaluation["findings"]) == 11
    assert all(item["status"] == "PASS" for item in evaluation["findings"])


@pytest.mark.parametrize(("changes", "services", "blocking_code"), [
    ({"patient_name": "Different Synthetic Patient"}, None, "IDENTITY_MATCH"),
    ({"valid_to": "2026-12-31"}, None, "DOCUMENT_VALID_ON_VISIT_DATE"),
    ({"clinic_id": "clinic-west"}, None, "CLINIC_ON_PANEL"),
    ({"organization_code": "UNKNOWN-ORG"}, None, "ORGANISATION_CODE_VALID"),
    ({"package_code": "UNKNOWN-PACKAGE"}, None, "PACKAGE_CODE_VALID"),
    ({}, ["MRI"], "REQUESTED_SERVICES_COVERED"),
])
def test_critical_mismatches_block_without_false_pass(client, changes, services, blocking_code):
    fields = {**BASE_FIELDS, **changes}
    _, evaluation, _ = prepared_case(client, fields, services)
    assert evaluation["outcome"] == "BLOCKED"
    finding = next(item for item in evaluation["findings"] if item["code"] == blocking_code)
    assert finding["status"] == "FAIL"


def test_conflicting_documents_block(client):
    created, _, _ = prepared_case(client)
    with SessionLocal() as db:
        case = db.scalar(select(Case).where(Case.id == created["id"]))
        document = Document(
            case_id=case.id,
            expected_category="medical_chit",
            category="medical_chit",
            filename="conflict.pdf",
            media_type="application/pdf",
            page_count=1,
            sha256="b" * 64,
            storage_path="/tmp/conflict.pdf",
            status="COMPLETE",
            scan_status="CLEAN",
        )
        db.add(document)
        db.flush()
        db.add(FieldAssertion(
            case_id=case.id, document_id=document.id, field_name="package_code", raw_value="OTHER",
            normalized_value="OTHER", page=1, evidence_ids=["p1-conflict"], bounding_boxes=[[1, 1, 2, 2]],
            extraction_provider="fixture", support_status="CONFLICTING",
        ))
        db.flush()
        evaluation = evaluate_case(db, case)
        db.commit()
        result = serialize_evaluation(db, evaluation)
    assert result["outcome"] == "BLOCKED"
    assert next(item for item in result["findings"] if item["code"] == "DOCUMENT_CONFLICT_FREE")["status"] == "FAIL"


def test_correction_invalidates_and_prevents_stale_approval(client):
    created, _, assertions = prepared_case(client)
    client.post("/api/v1/auth/login", json={"email": "assistant@clinicpass.test", "password": "DemoAssistant1!"})
    corrected = client.patch(f"/api/v1/clinic/cases/{created['id']}/assertions/{assertions['package_code']}", json={
        "corrected_value": "UNKNOWN-PACKAGE",
        "reason": "Original synthetic document was re-read by staff",
    })
    assert corrected.status_code == 200
    approval = client.post(f"/api/v1/clinic/cases/{created['id']}/review", json={
        "action": "approve", "reason": "Attempt stale approval", "override_failures": False,
    })
    assert approval.status_code == 409
    evaluation = client.get(f"/api/v1/clinic/cases/{created['id']}/evaluation").json()
    assert evaluation["outcome"] == "BLOCKED"


def test_assistant_can_request_but_not_apply_override(client):
    created, evaluation, _ = prepared_case(client, {**BASE_FIELDS, "package_code": "UNKNOWN"})
    finding = next(item for item in evaluation["findings"] if item["code"] == "PACKAGE_CODE_VALID")
    client.post("/api/v1/auth/login", json={"email": "assistant@clinicpass.test", "password": "DemoAssistant1!"})
    payload = {"finding_id": finding["id"], "reason": "Synthetic exception needs manager review"}
    assert client.post(f"/api/v1/clinic/cases/{created['id']}/overrides", json=payload).status_code == 403
    assert client.post(f"/api/v1/clinic/cases/{created['id']}/override-requests", json=payload).status_code == 201


def test_staff_mutations_require_session_bound_csrf_token(client, monkeypatch):
    created, _, _ = prepared_case(client)
    monkeypatch.setattr(main_module.settings, "csrf_enabled", True)
    login = client.post("/api/v1/auth/login", json={
        "email": "assistant@clinicpass.test", "password": "DemoAssistant1!",
    })
    assert login.status_code == 200
    payload = {"action": "request_information", "reason": "Synthetic CSRF regression", "override_failures": False}
    blocked = client.post(f"/api/v1/clinic/cases/{created['id']}/review", json=payload)
    assert blocked.status_code == 403
    csrf = client.cookies.get("cp_csrf")
    allowed = client.post(
        f"/api/v1/clinic/cases/{created['id']}/review",
        json=payload,
        headers={"X-CSRF-Token": csrf},
    )
    assert allowed.status_code == 200


def test_upload_scanner_fails_closed_on_test_signature(client):
    created = client.post("/api/v1/patient/cases", json={
        "patient_name": "Synthetic Scan", "patient_email": "scan@example.test", "id_last4": "111A", "appointment_type": "walk-in",
    }).json()
    dangerous = image_bytes() + b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"
    response = client.post(f"/api/v1/patient/cases/{created['id']}/documents", files={"file": ("scan.png", dangerous, "image/png")})
    assert response.status_code == 422
    assert "security scanning" in response.json()["detail"]


def test_canonical_export_is_schema_valid_and_idempotent(client, monkeypatch):
    created, _, _ = prepared_case(client)
    client.post("/api/v1/auth/login", json={"email": "assistant@clinicpass.test", "password": "DemoAssistant1!"})
    approved = client.post(f"/api/v1/clinic/cases/{created['id']}/review", json={
        "action": "approve", "reason": "All synthetic evidence reviewed", "override_failures": False,
    })
    assert approved.status_code == 200
    for attestation_type in ["IDENTITY_DOCUMENT", "ECARD", "ORIGINAL_SUPPORTING_DOCUMENTS"]:
        assert client.post(f"/api/v1/clinic/cases/{created['id']}/check-in/attestations", json={"attestation_type": attestation_type, "confirmed": True}).status_code == 201

    captured = {}

    class MockClient:
        def __init__(self, **_): pass
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def post(self, url, **kwargs):
            captured["payload"] = json.loads(kwargs["content"])
            return httpx.Response(202, json={"status": "accepted", "reference": "CA-SYNTHETIC"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(main_module.httpx, "Client", MockClient)
    key = "synthetic-export-key-001"
    first = client.post(f"/api/v1/clinic/cases/{created['id']}/export", headers={"Idempotency-Key": key})
    assert first.status_code == 200
    schema_path = Path(__file__).parents[2] / "mock-clinic-assist" / "clinic-assist-v2.schema.json"
    Draft202012Validator(json.loads(schema_path.read_text())).validate(captured["payload"])
    second = client.post(f"/api/v1/clinic/cases/{created['id']}/export", headers={"Idempotency-Key": key})
    assert second.status_code == 200
    assert second.json()["idempotent_replay"] is True
