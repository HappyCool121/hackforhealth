from datetime import date
from types import SimpleNamespace
from app.rules import evaluate, readiness_status


def test_six_rules_are_deterministic():
    document = SimpleNamespace(
        id="doc-1",
        status="COMPLETE",
        category="screening_voucher",
        extracted_data={
            "id_last4": "123A",
            "valid_to": "2027-12-31",
            "clinic_id": "clinic-central",
            "organization_code": "ORG-DEMO",
            "package_code": "PKG-SCREEN",
            "billing_arrangement": "direct",
            "payer": "Demo Health Fund",
        },
    )
    case = SimpleNamespace(documents=[document], clinic_id="clinic-central", appointment_date=date(2027, 1, 1))
    results = evaluate(case)
    assert len(results) == 6
    assert all(result["status"] == "PASS" for result in results)
    assert readiness_status(results) == "READY_FOR_REVIEW"


def test_failures_require_action():
    case = SimpleNamespace(
        documents=[], clinic_id="clinic-central", appointment_date=None, document_requirement="yes"
    )
    results = evaluate(case)
    assert readiness_status(results) == "NEEDS_ACTION"
    assert {item["code"] for item in results} == {"identity", "validity", "clinic", "codes", "supporting", "billing"}


def test_no_document_declaration_requires_review_not_failure():
    case = SimpleNamespace(
        documents=[], clinic_id="clinic-central", appointment_date=None, document_requirement="no"
    )
    results = evaluate(case)
    supporting = next(item for item in results if item["code"] == "supporting")
    assert supporting["status"] == "REVIEW"
    assert readiness_status(results) == "READY_FOR_REVIEW"
