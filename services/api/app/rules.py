from __future__ import annotations
from datetime import date
from dateutil.parser import parse
from .models import Case


def _result(code: str, label: str, status: str, explanation: str, evidence: list[str] | None = None) -> dict:
    return {"code": code, "label": label, "status": status, "explanation": explanation, "evidence_document_ids": evidence or []}


def evaluate(case: Case) -> list[dict]:
    complete = [doc for doc in case.documents if doc.status == "COMPLETE"]
    fields = {}
    evidence_ids: list[str] = []
    for doc in complete:
        fields.update({key: value for key, value in doc.extracted_data.items() if value})
        evidence_ids.append(doc.id)

    identity = fields.get("id_last4") or fields.get("patient_name")
    identity_status = "PASS" if identity else "REVIEW"

    validity = fields.get("valid_to")
    validity_status = "REVIEW"
    if validity:
        try:
            comparison = case.appointment_date or date.today()
            validity_status = "PASS" if parse(str(validity)).date() >= comparison else "FAIL"
        except ValueError:
            validity_status = "REVIEW"

    clinic = fields.get("clinic_id")
    clinic_status = "PASS" if clinic == case.clinic_id else ("FAIL" if clinic else "REVIEW")
    codes = bool(fields.get("organization_code") and fields.get("package_code"))
    categories = {doc.category for doc in complete}
    supporting_categories = {
        "medical_chit",
        "referral",
        "healthier_sg",
        "government_checkup",
        "driver_license_renewal",
        "insurance_ecard",
        "screening_voucher",
        "authorization",
    }
    supporting = bool(categories.intersection(supporting_categories))
    requirement = getattr(case, "document_requirement", "yes")
    if supporting:
        supporting_status = "PASS"
        supporting_explanation = "At least one supporting document was received."
    elif requirement in {"no", "unsure"}:
        supporting_status = "REVIEW"
        supporting_explanation = "The patient declared that documents are not needed or was unsure; staff must confirm."
    else:
        supporting_status = "FAIL"
        supporting_explanation = "The patient declared documents are needed, but no supported document was processed."
    billing = bool(fields.get("billing_arrangement") and fields.get("payer"))

    return [
        _result("identity", "Identity details", identity_status, "Document identity details must be confirmed on site.", evidence_ids),
        _result("validity", "Document validity", validity_status, "Validity must cover the visit date.", evidence_ids),
        _result("clinic", "Clinic and location", clinic_status, "The named clinic must match this registration.", evidence_ids),
        _result("codes", "Organisation and package", "PASS" if codes else "REVIEW", "Both administrative codes are required.", evidence_ids),
        _result("supporting", "Supporting documents", supporting_status, supporting_explanation, evidence_ids),
        _result("billing", "Billing completeness", "PASS" if billing else "REVIEW", "Payer and billing arrangement must be present.", evidence_ids),
    ]


def readiness_status(rules: list[dict]) -> str:
    return "NEEDS_ACTION" if any(rule["status"] == "FAIL" for rule in rules) else "READY_FOR_REVIEW"
