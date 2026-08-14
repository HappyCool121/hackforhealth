from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .models import (
    BillingRule,
    Case,
    ClinicPanelRule,
    EligibilityContract,
    Document,
    PackageProcedure,
    PackageVersion,
    PatientProfile,
    PayerOrganisation,
    Procedure,
    ReferenceDataRelease,
)
from .security import get_upload_scanner, identity_hash, mask_identity


REFERENCE_VERSION = "demo-2026.08.1"


def seed_v2_reference_data(db: Session) -> ReferenceDataRelease:
    release = db.scalar(select(ReferenceDataRelease).where(ReferenceDataRelease.version == REFERENCE_VERSION))
    if release:
        return release
    db.execute(update(ReferenceDataRelease).values(active=False))
    release = ReferenceDataRelease(
        version=REFERENCE_VERSION,
        description="Synthetic ClinicPass judging reference data; no real payer or scheme connectivity.",
        active=True,
        activated_at=datetime.now(timezone.utc),
    )
    db.add(release)
    db.flush()
    payer = PayerOrganisation(
        release_id=release.id,
        code="PAYER-DEMO",
        name="Demo Health Fund",
        organisation_type="insurer",
        issuer_aliases=["Northstar Corporate Benefits", "Demo Health Organisation"],
    )
    db.add(payer)
    db.flush()
    contract = EligibilityContract(
        release_id=release.id,
        payer_organisation_id=payer.id,
        organisation_code="ORG-DEMO",
        policy_reference="POLICY-SYNTHETIC-001",
        effective_from=date(2026, 1, 1),
        effective_to=date(2027, 12, 31),
    )
    db.add(contract)
    db.flush()
    package = PackageVersion(
        release_id=release.id,
        contract_id=contract.id,
        code="PKG-SCREEN",
        name="Synthetic Preventive Screening Package",
        effective_from=date(2026, 1, 1),
        effective_to=date(2027, 12, 31),
        required_documents=["medical_chit"],
        restrictions={"provisional_only": True},
    )
    db.add(package)
    db.flush()
    for code, name, aliases, coverage in [
        ("BASIC_SCREEN", "Basic health screening", ["basic screening", "health screening"], "INCLUDED"),
        ("CBC", "Full blood count", ["complete blood count", "full blood count"], "INCLUDED"),
        ("CHEST_XRAY", "Chest X-ray", ["chest radiograph"], "CONDITIONAL"),
        ("MRI", "Magnetic resonance imaging", ["mri scan"], "EXCLUDED"),
    ]:
        procedure = Procedure(release_id=release.id, code=code, name=name, aliases=aliases)
        db.add(procedure)
        db.flush()
        db.add(PackageProcedure(package_version_id=package.id, procedure_id=procedure.id, coverage=coverage))
    db.add(ClinicPanelRule(release_id=release.id, contract_id=contract.id, clinic_id="clinic-central", location_code="CENTRAL", permitted=True))
    db.add(BillingRule(
        release_id=release.id,
        contract_id=contract.id,
        package_version_id=package.id,
        payer=payer.name,
        arrangement="direct",
        billing_code="BILL-DEMO-SCREEN",
    ))
    db.flush()
    return release


def backfill_v2(db: Session) -> None:
    """Add normalized profiles without inventing facts or changing terminal history."""
    for case in db.scalars(select(Case)).all():
        profile = db.scalar(select(PatientProfile).where(PatientProfile.case_id == case.id))
        if not profile:
            synthetic_identity = f"LEGACY-{case.id_last4}"
            db.add(PatientProfile(
                case_id=case.id,
                full_name=case.patient_name,
                identity_type="legacy_fragment",
                identity_number_encrypted=None,
                identity_hash=identity_hash(synthetic_identity),
                masked_identity=mask_identity(case.id_last4),
                email=case.patient_email,
                provider=case.identity_source,
                confirmed_at=None,
            ))
            if case.status not in {"DRAFT", "CANCELLED", "EXPORTED", "COMPLETED"}:
                case.status = "NEEDS_ACTION"
                case.rules = []
        if case.requested_services is None:
            case.requested_services = []
    scanner = get_upload_scanner()
    for document in db.scalars(select(Document).where(Document.scan_status == "PENDING_SCAN")).all():
        if document.content:
            clean, _ = scanner.scan(document.content, document.filename, document.media_type)
            document.scan_status = "CLEAN" if clean else "REJECTED"
            if not clean and document.status in {"QUEUED", "PROCESSING"}:
                document.status = "ERROR"
                document.error = "Legacy upload failed V2 security scanning"
        elif document.status in {"COMPLETE", "ERROR"}:
            document.scan_status = "LEGACY_NOT_RETAINED"
        else:
            document.scan_status = "SCAN_FAILED"
            document.status = "ERROR"
            document.error = "Legacy upload bytes were unavailable for mandatory V2 scanning"
    db.flush()
