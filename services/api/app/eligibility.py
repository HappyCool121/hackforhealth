from __future__ import annotations

from collections import defaultdict
from datetime import date
import hashlib
import json
from typing import Any

from dateutil.parser import parse
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .models import (
    BillingRule,
    Case,
    ClinicPanelRule,
    EligibilityContract,
    EligibilityEvaluation,
    FieldAssertion,
    FindingOverride,
    PackageProcedure,
    PackageVersion,
    PatientProfile,
    PayerOrganisation,
    Procedure,
    ReferenceDataRelease,
    RuleFinding,
    StaffCorrection,
)


RULESET_VERSION = "clinicpass-eligibility-2.0.0"
CRITICAL_FAILURES = {
    "IDENTITY_MATCH",
    "ISSUER_RECOGNISED",
    "DOCUMENT_VALID_ON_VISIT_DATE",
    "ORGANISATION_CODE_VALID",
    "PACKAGE_CODE_VALID",
    "PACKAGE_ACTIVE_ON_VISIT_DATE",
    "CLINIC_ON_PANEL",
    "REQUESTED_SERVICES_COVERED",
    "SUPPORTING_DOCUMENTS_COMPLETE",
    "DOCUMENT_CONFLICT_FREE",
}


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    if isinstance(value, (date,)):
        return value.isoformat()
    return value


def current_input_hash(db: Session, case: Case) -> str:
    profile = db.scalar(select(PatientProfile).where(PatientProfile.case_id == case.id))
    assertions = db.scalars(select(FieldAssertion).where(FieldAssertion.case_id == case.id)).all()
    corrections = db.scalars(select(StaffCorrection).where(StaffCorrection.case_id == case.id)).all()
    release = db.scalar(select(ReferenceDataRelease).where(ReferenceDataRelease.active.is_(True)))
    payload = {
        "case": {
            "patient_name": case.patient_name,
            "id_last4": case.id_last4,
            "appointment_type": case.appointment_type,
            "appointment_date": case.appointment_date,
            "visit_reason": case.visit_reason,
            "document_requirement": case.document_requirement,
            "clinic_id": case.clinic_id,
            "requested_services": case.requested_services or [],
        },
        "profile": {
            "full_name": profile.full_name,
            "identity_hash": profile.identity_hash,
            "masked_identity": profile.masked_identity,
            "date_of_birth": profile.date_of_birth,
        } if profile else None,
        "documents": [
            {"id": doc.id, "sha256": doc.sha256, "status": doc.status, "scan_status": doc.scan_status}
            for doc in sorted(case.documents, key=lambda item: item.id)
        ],
        "assertions": [
            {
                "id": item.id,
                "field": item.field_name,
                "value": item.normalized_value,
                "support": item.support_status,
                "document": item.document_id,
            }
            for item in sorted(assertions, key=lambda item: item.id)
        ],
        "corrections": [
            {"assertion": item.assertion_id, "value": item.corrected_value, "created_at": item.created_at.isoformat()}
            for item in sorted(corrections, key=lambda item: item.id)
        ],
        "reference_data_version": release.version if release else "none",
    }
    encoded = json.dumps(_canonical(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def invalidate_evaluations(db: Session, case_id: str) -> None:
    db.execute(
        update(EligibilityEvaluation)
        .where(EligibilityEvaluation.case_id == case_id, EligibilityEvaluation.stale.is_(False))
        .values(stale=True)
    )


def _field_values(db: Session, case: Case) -> tuple[dict[str, str], dict[str, list[FieldAssertion]], set[str]]:
    assertions = db.scalars(select(FieldAssertion).where(FieldAssertion.case_id == case.id)).all()
    by_field: dict[str, list[FieldAssertion]] = defaultdict(list)
    for assertion in assertions:
        by_field[assertion.field_name].append(assertion)
    corrections = {
        correction.assertion_id: correction.corrected_value
        for correction in db.scalars(select(StaffCorrection).where(StaffCorrection.case_id == case.id).order_by(StaffCorrection.created_at)).all()
    }
    values: dict[str, str] = {}
    conflicts: set[str] = set()
    for field_name, items in by_field.items():
        authoritative = [
            item for item in items
            if item.support_status in {"SUPPORTED", "STAFF_CORRECTED", "CONFLICTING"} or item.id in corrections
        ]
        supported_values = {
            (corrections.get(item.id) or item.normalized_value or "").strip().casefold()
            for item in authoritative
        } - {""}
        if len(supported_values) > 1 or any(item.support_status == "CONFLICTING" for item in items):
            conflicts.add(field_name)
        if authoritative:
            latest = authoritative[-1]
            values[field_name] = corrections.get(latest.id) or latest.normalized_value or ""
    return values, by_field, conflicts


def _finding(code: str, status: str, explanation: str, assertions: list[FieldAssertion] | None = None, refs: list[str] | None = None) -> dict:
    return {
        "code": code,
        "status": status,
        "critical": code in CRITICAL_FAILURES,
        "explanation": explanation,
        "evidence_assertion_ids": [item.id for item in assertions or []],
        "reference_record_ids": refs or [],
    }


def _visit_date(case: Case) -> date:
    return case.appointment_date or date.today()


def evaluate_case(db: Session, case: Case) -> EligibilityEvaluation:
    release = db.scalar(select(ReferenceDataRelease).where(ReferenceDataRelease.active.is_(True)))
    if not release:
        raise RuntimeError("No active reference-data release")
    values, assertions, conflicts = _field_values(db, case)
    profile = db.scalar(select(PatientProfile).where(PatientProfile.case_id == case.id))
    visit_date = _visit_date(case)

    identity_name = values.get("patient_name", "").strip().casefold()
    identity_last4 = values.get("id_last4", "").strip().upper()
    expected_name = (profile.full_name if profile else case.patient_name).strip().casefold()
    expected_last4 = case.id_last4.strip().upper()
    if not identity_name and not identity_last4:
        identity_status, identity_text = "REVIEW", "Documentary identity is unknown; verify it in person."
    elif (identity_name and identity_name != expected_name) or (identity_last4 and identity_last4 != expected_last4):
        identity_status, identity_text = "FAIL", "Documentary identity does not match the patient-entered identity."
    elif identity_name and identity_last4:
        identity_status, identity_text = "PASS", "Name and identifier fragment match the patient profile."
    else:
        identity_status, identity_text = "REVIEW", "Only one documentary identity attribute matched; staff confirmation is required."

    issuer = values.get("issuer", "").strip().casefold()
    payers = db.scalars(select(PayerOrganisation).where(PayerOrganisation.release_id == release.id, PayerOrganisation.active.is_(True))).all()
    payer = next((row for row in payers if issuer and issuer in {row.name.casefold(), row.code.casefold(), *[str(alias).casefold() for alias in row.issuer_aliases]}), None)
    issuer_status = "PASS" if payer else ("FAIL" if issuer else "REVIEW")
    issuer_text = "Issuer matches active synthetic reference data." if payer else ("Issuer is not recognised in the active reference release." if issuer else "Issuer was not extracted.")

    valid_to = values.get("valid_to", "")
    if not valid_to:
        validity_status, validity_text = "REVIEW", "A validity end date was not available."
    else:
        try:
            valid = parse(valid_to).date() >= visit_date
            validity_status = "PASS" if valid else "FAIL"
            validity_text = "Document covers the visit date." if valid else "Document expires before the visit date."
        except (ValueError, TypeError, OverflowError):
            validity_status, validity_text = "REVIEW", "The extracted validity date could not be interpreted."

    organisation_code = values.get("organization_code", "").strip().upper()
    contract = db.scalar(select(EligibilityContract).where(
        EligibilityContract.release_id == release.id,
        EligibilityContract.organisation_code == organisation_code,
        EligibilityContract.active.is_(True),
    )) if organisation_code else None
    org_status = "PASS" if contract else ("FAIL" if organisation_code else "REVIEW")
    org_text = "Organisation code matches an active contract." if contract else ("Organisation code is unknown." if organisation_code else "Organisation code was not extracted.")

    package_code = values.get("package_code", "").strip().upper()
    package = db.scalar(select(PackageVersion).where(PackageVersion.release_id == release.id, PackageVersion.code == package_code, PackageVersion.active.is_(True))) if package_code else None
    package_status = "PASS" if package else ("FAIL" if package_code else "REVIEW")
    package_text = "Package code exists in the active release." if package else ("Package code is unknown." if package_code else "Package code was not extracted.")
    if package:
        package_active = package.effective_from <= visit_date <= package.effective_to and (not contract or package.contract_id == contract.id)
        package_active_status = "PASS" if package_active else "FAIL"
        package_active_text = "Package is active for the visit date and contract." if package_active else "Package is inactive for the visit date or organisation contract."
    else:
        package_active_status, package_active_text = "REVIEW", "Package activity cannot be determined without a valid package."

    documented_clinic = values.get("clinic_id", "").strip()
    panel = db.scalar(select(ClinicPanelRule).where(
        ClinicPanelRule.release_id == release.id,
        ClinicPanelRule.contract_id == contract.id,
        ClinicPanelRule.clinic_id == case.clinic_id,
        ClinicPanelRule.permitted.is_(True),
    )) if contract else None
    if documented_clinic and documented_clinic != case.clinic_id:
        panel_status, panel_text = "FAIL", "The document names a different clinic from this registration."
    else:
        panel_status = "PASS" if panel else ("FAIL" if contract else "REVIEW")
        panel_text = "Clinic is on the contract panel." if panel else ("Clinic is not on the contract panel." if contract else "Panel status cannot be resolved without a contract.")

    requested = {str(item).strip().upper() for item in (case.requested_services or []) if str(item).strip()}
    if not requested:
        services_status, services_text, service_refs = "REVIEW", "No canonical requested services were selected.", []  # type: str, str, list[str]
    elif not package:
        services_status, services_text, service_refs = "REVIEW", "Coverage cannot be resolved without a valid package.", []
    else:
        rows = db.execute(
            select(Procedure, PackageProcedure)
            .join(PackageProcedure, PackageProcedure.procedure_id == Procedure.id)
            .where(PackageProcedure.package_version_id == package.id)
        ).all()
        coverage = {procedure.code.upper(): (mapping.coverage, mapping.id) for procedure, mapping in rows}
        missing = sorted(code for code in requested if code not in coverage or coverage[code][0] == "EXCLUDED")
        conditional = sorted(code for code in requested if code in coverage and coverage[code][0] == "CONDITIONAL")
        service_refs = [coverage[code][1] for code in requested if code in coverage]
        if missing:
            services_status, services_text = "FAIL", f"Requested services are not covered: {', '.join(missing)}."
        elif conditional:
            services_status, services_text = "REVIEW", f"Conditional services need staff review: {', '.join(conditional)}."
        else:
            services_status, services_text = "PASS", "All requested services are included in the package."

    completed_categories = {doc.category for doc in case.documents if doc.status == "COMPLETE"}
    if case.document_requirement in {"no", "unsure"} and not case.documents:
        docs_status, docs_text = "REVIEW", "Patient declared no document or was unsure; staff must confirm."
    elif package and set(package.required_documents).issubset(completed_categories):
        docs_status, docs_text = "PASS", "All package-required supporting document categories are complete."
    elif case.document_requirement == "yes":
        docs_status, docs_text = "FAIL", "Required supporting documents are missing or incomplete."
    else:
        docs_status, docs_text = "REVIEW", "Supporting-document completeness needs staff review."

    billing = db.scalar(select(BillingRule).where(
        BillingRule.release_id == release.id,
        BillingRule.contract_id == contract.id,
        BillingRule.package_version_id == package.id,
    )) if contract and package else None
    billing_status = "PASS" if billing else "REVIEW"
    billing_text = "Billing route resolved from versioned reference data." if billing else "Billing route could not be resolved."

    conflict_status = "FAIL" if conflicts else "PASS"
    conflict_text = f"Conflicting values require resolution: {', '.join(sorted(conflicts))}." if conflicts else "No conflicting supported document facts were found."

    candidates = [
        _finding("IDENTITY_MATCH", identity_status, identity_text, assertions.get("patient_name", []) + assertions.get("id_last4", [])),
        _finding("ISSUER_RECOGNISED", issuer_status, issuer_text, assertions.get("issuer", []), [payer.id] if payer else []),
        _finding("DOCUMENT_VALID_ON_VISIT_DATE", validity_status, validity_text, assertions.get("valid_to", [])),
        _finding("ORGANISATION_CODE_VALID", org_status, org_text, assertions.get("organization_code", []), [contract.id] if contract else []),
        _finding("PACKAGE_CODE_VALID", package_status, package_text, assertions.get("package_code", []), [package.id] if package else []),
        _finding("PACKAGE_ACTIVE_ON_VISIT_DATE", package_active_status, package_active_text, assertions.get("package_code", []), [package.id] if package else []),
        _finding("CLINIC_ON_PANEL", panel_status, panel_text, assertions.get("clinic_id", []), [panel.id] if panel else []),
        _finding("REQUESTED_SERVICES_COVERED", services_status, services_text, assertions.get("requested_services", []), service_refs),
        _finding("SUPPORTING_DOCUMENTS_COMPLETE", docs_status, docs_text),
        _finding("BILLING_ROUTE_RESOLVED", billing_status, billing_text, assertions.get("billing_arrangement", []), [billing.id] if billing else []),
        _finding("DOCUMENT_CONFLICT_FREE", conflict_status, conflict_text, [item for field in conflicts for item in assertions[field]]),
    ]
    input_hash = current_input_hash(db, case)
    invalidate_evaluations(db, case.id)
    blocking = any(item["critical"] and item["status"] == "FAIL" for item in candidates)
    review = any(item["status"] == "REVIEW" for item in candidates)
    outcome = "BLOCKED" if blocking else ("REVIEW_REQUIRED" if review else "PROVISIONALLY_ELIGIBLE")
    evaluation = EligibilityEvaluation(
        case_id=case.id,
        ruleset_version=RULESET_VERSION,
        reference_data_version=release.version,
        input_hash=input_hash,
        outcome=outcome,
        stale=False,
    )
    db.add(evaluation)
    db.flush()
    for item in candidates:
        db.add(RuleFinding(evaluation_id=evaluation.id, **item))
    case.rules = [
        {
            "code": item["code"],
            "label": item["code"].replace("_", " ").title(),
            "status": item["status"],
            "explanation": item["explanation"],
            "evidence_document_ids": sorted({assertion.document_id for assertion in assertions.get("patient_name", [])}) if item["code"] == "IDENTITY_MATCH" else [],
        }
        for item in candidates
    ]
    return evaluation


def latest_evaluation(db: Session, case_id: str) -> EligibilityEvaluation | None:
    return db.scalar(
        select(EligibilityEvaluation)
        .where(EligibilityEvaluation.case_id == case_id)
        .order_by(EligibilityEvaluation.evaluated_at.desc(), EligibilityEvaluation.id.desc())
    )


def serialize_evaluation(db: Session, evaluation: EligibilityEvaluation) -> dict:
    findings = db.scalars(select(RuleFinding).where(RuleFinding.evaluation_id == evaluation.id)).all()
    overrides = {row.finding_id: row for row in db.scalars(select(FindingOverride).where(FindingOverride.case_id == evaluation.case_id)).all()}
    return {
        "id": evaluation.id,
        "ruleset_version": evaluation.ruleset_version,
        "reference_data_version": evaluation.reference_data_version,
        "input_hash": evaluation.input_hash,
        "evaluated_at": evaluation.evaluated_at.isoformat(),
        "outcome": evaluation.outcome,
        "stale": evaluation.stale,
        "findings": [
            {
                "id": row.id,
                "code": row.code,
                "status": row.status,
                "critical": row.critical,
                "explanation": row.explanation,
                "evidence_assertion_ids": row.evidence_assertion_ids,
                "reference_record_ids": row.reference_record_ids,
                "override": {
                    "reason": overrides[row.id].reason,
                    "actor_role": overrides[row.id].actor_role,
                    "created_at": overrides[row.id].created_at.isoformat(),
                } if row.id in overrides else None,
            }
            for row in findings
        ],
    }
