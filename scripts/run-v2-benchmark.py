from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import sys
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import Session


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.db import Base  # noqa: E402
from app.eligibility import RULESET_VERSION, evaluate_case, serialize_evaluation  # noqa: E402
from app.models import Case, Document, FieldAssertion, PatientProfile  # noqa: E402
from app.questionnaires import QUESTIONNAIRE_DEFINITIONS  # noqa: E402
from app.reference_seed import REFERENCE_VERSION, seed_v2_reference_data  # noqa: E402
from app.security import identity_hash, mask_identity  # noqa: E402


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


def build_case(db: Session, scenario: dict) -> Case:
    case = Case(
        reference=f"BENCH-{scenario['id'][:12]}",
        patient_name="Synthetic Jamie Tan",
        patient_email=f"{scenario['id']}@example.test",
        id_last4="123A",
        appointment_type="scheduled",
        appointment_date=date(2027, 1, 10),
        visit_reason="corporate_insurer_screening",
        document_requirement="no" if scenario.get("mode") == "documentless" else "yes",
        identity_source="manual",
        requested_services=scenario.get("requested_services", ["BASIC_SCREEN"]),
        clinic_id="clinic-central",
        patient_token_hash=identity_hash(f"token-{scenario['id']}"),
    )
    db.add(case)
    db.flush()
    db.add(PatientProfile(
        case_id=case.id,
        full_name=case.patient_name,
        identity_hash=identity_hash("S000123A"),
        masked_identity=mask_identity("S000123A"),
        email=case.patient_email,
    ))
    if scenario.get("mode") == "documentless":
        db.flush()
        return case
    status = "ERROR" if scenario.get("mode") == "provider_failure" else "COMPLETE"
    document = Document(
        case_id=case.id,
        expected_category="medical_chit",
        category="medical_chit" if status == "COMPLETE" else None,
        filename=f"{scenario['id']}.pdf",
        media_type="application/pdf",
        page_count=1,
        sha256=identity_hash(scenario["id"]),
        storage_path=f"/tmp/{scenario['id']}.pdf",
        status=status,
        scan_status="CLEAN",
    )
    db.add(document)
    db.flush()
    if status == "ERROR":
        return case
    fields = {**BASE_FIELDS, **scenario.get("change", {})}
    for field_name, value in fields.items():
        supported = scenario.get("mode") != "unsupported"
        db.add(FieldAssertion(
            case_id=case.id,
            document_id=document.id,
            field_name=field_name,
            raw_value=value,
            normalized_value=value,
            page=1 if supported else None,
            evidence_ids=[f"p1-{field_name}"] if supported else [],
            bounding_boxes=[[10, 10, 100, 30]] if supported else [],
            extraction_provider="fixture",
            support_status="SUPPORTED" if supported else "UNSUPPORTED",
            validation_errors=[] if supported else ["Low-quality fixture has no reliable citation"],
        ))
    if scenario.get("mode") == "conflict":
        db.add(FieldAssertion(
            case_id=case.id,
            document_id=document.id,
            field_name="package_code",
            raw_value="CONFLICTING-PACKAGE",
            normalized_value="CONFLICTING-PACKAGE",
            page=1,
            evidence_ids=["p1-conflict"],
            bounding_boxes=[[20, 20, 120, 40]],
            extraction_provider="fixture",
            support_status="CONFLICTING",
        ))
    db.flush()
    return case


def main() -> int:
    manifest_path = ROOT / "fixtures" / "synthetic" / "v2-benchmark-manifest.json"
    output_path = ROOT / "output" / "benchmark" / "clinicpass-v2-results.json"
    manifest = json.loads(manifest_path.read_text())
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    results = []
    latencies = []
    with Session(engine) as db:
        seed_v2_reference_data(db)
        for scenario in manifest["scenarios"]:
            case = build_case(db, scenario)
            started = time.perf_counter()
            evaluation = evaluate_case(db, case)
            latency_ms = (time.perf_counter() - started) * 1000
            latencies.append(latency_ms)
            result = serialize_evaluation(db, evaluation)
            results.append({
                "id": scenario["id"],
                "expected_outcome": scenario["expected_outcome"],
                "actual_outcome": result["outcome"],
                "passed": result["outcome"] == scenario["expected_outcome"],
                "evaluation_latency_ms": round(latency_ms, 3),
            })
    blocking = [item for item in results if item["expected_outcome"] == "BLOCKED"]
    false_passes = [item for item in blocking if item["actual_outcome"] == "PROVISIONALLY_ELIGIBLE"]
    ordered = sorted(latencies)
    report = {
        "manifest_version": manifest["manifest_version"],
        "ruleset_version": RULESET_VERSION,
        "reference_data_version": REFERENCE_VERSION,
        "generated_from_synthetic_data_only": True,
        "scope": manifest["scope"],
        "scenario_pass_rate": sum(item["passed"] for item in results) / len(results),
        "false_pass_rate_on_blocking_set": len(false_passes) / len(blocking),
        "evidence_policy": "Every asserted fixture field has citations or is explicitly UNSUPPORTED/CONFLICTING.",
        "prefill_fields_available": len(QUESTIONNAIRE_DEFINITIONS["general-health"]["prefill_fields"]),
        "deterministic_evaluation_latency_ms": {
            "p50": round(ordered[len(ordered) // 2], 3),
            "p95": round(ordered[min(len(ordered) - 1, round((len(ordered) - 1) * 0.95))], 3),
        },
        "not_measured_here": [
            "live extraction exact match", "manual correction rate", "human review time",
            "ready-before-arrival rate", "live provider cost per case",
        ],
        "scenarios": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Wrote {output_path}")
    return 0 if all(item["passed"] for item in results) and not false_passes else 1


if __name__ == "__main__":
    raise SystemExit(main())
