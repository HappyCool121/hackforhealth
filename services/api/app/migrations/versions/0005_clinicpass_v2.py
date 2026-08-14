"""Add the rollback-safe ClinicPass V2 eligibility model.

Revision ID: 0005_clinicpass_v2
Revises: 0004_durable_document_content
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_clinicpass_v2"
down_revision = "0004_durable_document_content"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("requested_services", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("documents", sa.Column("scan_status", sa.String(length=30), nullable=False, server_default="PENDING_SCAN"))
    op.add_column("audit_events", sa.Column("previous_digest", sa.String(length=64), nullable=True))
    op.add_column("audit_events", sa.Column("integrity_digest", sa.String(length=64), nullable=True))
    op.create_index("ix_audit_events_integrity_digest", "audit_events", ["integrity_digest"], unique=True)

    op.create_table(
        "reference_data_releases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reference_data_releases_version", "reference_data_releases", ["version"], unique=True)
    op.create_index("ix_reference_data_releases_active", "reference_data_releases", ["active"])

    op.create_table(
        "payer_organisations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("release_id", sa.String(36), sa.ForeignKey("reference_data_releases.id"), nullable=False),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("organisation_type", sa.String(30), nullable=False),
        sa.Column("issuer_aliases", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("release_id", "code", name="uq_payer_release_code"),
    )
    op.create_index("ix_payer_organisations_release_id", "payer_organisations", ["release_id"])
    op.create_table(
        "eligibility_contracts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("release_id", sa.String(36), sa.ForeignKey("reference_data_releases.id"), nullable=False),
        sa.Column("payer_organisation_id", sa.String(36), sa.ForeignKey("payer_organisations.id"), nullable=False),
        sa.Column("organisation_code", sa.String(60), nullable=False),
        sa.Column("policy_reference", sa.String(100), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("release_id", "organisation_code", name="uq_contract_release_code"),
    )
    op.create_index("ix_eligibility_contracts_release_id", "eligibility_contracts", ["release_id"])
    op.create_index("ix_eligibility_contracts_organisation_code", "eligibility_contracts", ["organisation_code"])
    op.create_table(
        "package_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("release_id", sa.String(36), sa.ForeignKey("reference_data_releases.id"), nullable=False),
        sa.Column("contract_id", sa.String(36), sa.ForeignKey("eligibility_contracts.id"), nullable=False),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=False),
        sa.Column("required_documents", sa.JSON(), nullable=False),
        sa.Column("restrictions", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("release_id", "code", name="uq_package_release_code"),
    )
    op.create_index("ix_package_versions_release_id", "package_versions", ["release_id"])
    op.create_index("ix_package_versions_code", "package_versions", ["code"])
    op.create_table(
        "procedures",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("release_id", sa.String(36), sa.ForeignKey("reference_data_releases.id"), nullable=False),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.UniqueConstraint("release_id", "code", name="uq_procedure_release_code"),
    )
    op.create_index("ix_procedures_release_id", "procedures", ["release_id"])
    op.create_table(
        "package_procedures",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("package_version_id", sa.String(36), sa.ForeignKey("package_versions.id"), nullable=False),
        sa.Column("procedure_id", sa.String(36), sa.ForeignKey("procedures.id"), nullable=False),
        sa.Column("coverage", sa.String(20), nullable=False),
        sa.Column("condition", sa.Text(), nullable=True),
        sa.UniqueConstraint("package_version_id", "procedure_id", name="uq_package_procedure"),
    )
    op.create_index("ix_package_procedures_package_version_id", "package_procedures", ["package_version_id"])
    op.create_table(
        "clinic_panel_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("release_id", sa.String(36), sa.ForeignKey("reference_data_releases.id"), nullable=False),
        sa.Column("contract_id", sa.String(36), sa.ForeignKey("eligibility_contracts.id"), nullable=False),
        sa.Column("clinic_id", sa.String(50), nullable=False),
        sa.Column("location_code", sa.String(60), nullable=True),
        sa.Column("permitted", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_clinic_panel_rules_release_id", "clinic_panel_rules", ["release_id"])
    op.create_index("ix_clinic_panel_rules_clinic_id", "clinic_panel_rules", ["clinic_id"])
    op.create_table(
        "billing_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("release_id", sa.String(36), sa.ForeignKey("reference_data_releases.id"), nullable=False),
        sa.Column("contract_id", sa.String(36), sa.ForeignKey("eligibility_contracts.id"), nullable=False),
        sa.Column("package_version_id", sa.String(36), sa.ForeignKey("package_versions.id"), nullable=True),
        sa.Column("payer", sa.String(180), nullable=False),
        sa.Column("arrangement", sa.String(60), nullable=False),
        sa.Column("billing_code", sa.String(60), nullable=False),
    )
    op.create_index("ix_billing_rules_release_id", "billing_rules", ["release_id"])

    op.create_table(
        "patient_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("identity_type", sa.String(30), nullable=False),
        sa.Column("identity_number_encrypted", sa.Text(), nullable=True),
        sa.Column("identity_hash", sa.String(64), nullable=False),
        sa.Column("masked_identity", sa.String(20), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("country_code", sa.String(8), nullable=False),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("postal_code", sa.String(20), nullable=True),
        sa.Column("ethnicity", sa.String(60), nullable=True),
        sa.Column("sex", sa.String(30), nullable=True),
        sa.Column("pregnancy_details", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(80), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("case_id"),
    )
    op.create_index("ix_patient_profiles_case_id", "patient_profiles", ["case_id"], unique=True)
    op.create_index("ix_patient_profiles_identity_hash", "patient_profiles", ["identity_hash"])
    op.create_table(
        "questionnaire_submissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("questionnaire_type", sa.String(50), nullable=False),
        sa.Column("definition_version", sa.String(30), nullable=False),
        sa.Column("responses", sa.JSON(), nullable=False),
        sa.Column("consents", sa.JSON(), nullable=False),
        sa.Column("signature_metadata", sa.JSON(), nullable=False),
        sa.Column("confirmed_prefill_fields", sa.JSON(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("case_id", "questionnaire_type", name="uq_case_questionnaire"),
    )
    op.create_index("ix_questionnaire_submissions_case_id", "questionnaire_submissions", ["case_id"])
    op.create_table(
        "field_assertions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=True),
        sa.Column("normalized_value", sa.Text(), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("bounding_boxes", sa.JSON(), nullable=False),
        sa.Column("extraction_provider", sa.String(30), nullable=False),
        sa.Column("support_status", sa.String(30), nullable=False),
        sa.Column("validation_errors", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_field_assertions_case_id", "field_assertions", ["case_id"])
    op.create_index("ix_field_assertions_document_id", "field_assertions", ["document_id"])
    op.create_index("ix_field_assertions_field_name", "field_assertions", ["field_name"])
    op.create_table(
        "staff_corrections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("assertion_id", sa.String(36), sa.ForeignKey("field_assertions.id"), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("original_value", sa.Text(), nullable=True),
        sa.Column("corrected_value", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_staff_corrections_case_id", "staff_corrections", ["case_id"])
    op.create_index("ix_staff_corrections_assertion_id", "staff_corrections", ["assertion_id"])

    op.create_table(
        "eligibility_evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("ruleset_version", sa.String(40), nullable=False),
        sa.Column("reference_data_version", sa.String(40), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.String(40), nullable=False),
        sa.Column("stale", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_eligibility_evaluations_case_id", "eligibility_evaluations", ["case_id"])
    op.create_index("ix_eligibility_evaluations_input_hash", "eligibility_evaluations", ["input_hash"])
    op.create_index("ix_eligibility_evaluations_stale", "eligibility_evaluations", ["stale"])
    op.create_table(
        "rule_findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("evaluation_id", sa.String(36), sa.ForeignKey("eligibility_evaluations.id"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("critical", sa.Boolean(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("evidence_assertion_ids", sa.JSON(), nullable=False),
        sa.Column("reference_record_ids", sa.JSON(), nullable=False),
    )
    op.create_index("ix_rule_findings_evaluation_id", "rule_findings", ["evaluation_id"])
    op.create_table(
        "override_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("finding_id", sa.String(36), sa.ForeignKey("rule_findings.id"), nullable=False),
        sa.Column("requested_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_override_requests_case_id", "override_requests", ["case_id"])
    op.create_index("ix_override_requests_finding_id", "override_requests", ["finding_id"])
    op.create_table(
        "finding_overrides",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("finding_id", sa.String(36), sa.ForeignKey("rule_findings.id"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_role", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("finding_id", name="uq_finding_override"),
    )
    op.create_index("ix_finding_overrides_case_id", "finding_overrides", ["case_id"])
    op.create_index("ix_finding_overrides_finding_id", "finding_overrides", ["finding_id"])
    op.create_table(
        "review_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("evaluation_id", sa.String(36), sa.ForeignKey("eligibility_evaluations.id"), nullable=True),
        sa.Column("decision", sa.String(40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_review_decisions_case_id", "review_decisions", ["case_id"])
    op.create_table(
        "on_site_attestations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("attestation_type", sa.String(40), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("attested_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("case_id", "attestation_type", name="uq_case_attestation"),
    )
    op.create_index("ix_on_site_attestations_case_id", "on_site_attestations", ["case_id"])
    op.create_table(
        "integration_exports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("schema_version", sa.String(20), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("case_id", "idempotency_key", name="uq_case_idempotency"),
    )
    op.create_index("ix_integration_exports_case_id", "integration_exports", ["case_id"])
    op.create_table(
        "processing_metrics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("dimensions", sa.JSON(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_processing_metrics_case_id", "processing_metrics", ["case_id"])
    op.create_index("ix_processing_metrics_name", "processing_metrics", ["name"])
    op.create_table(
        "benchmark_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("fixture_manifest_version", sa.String(40), nullable=False),
        sa.Column("ruleset_version", sa.String(40), nullable=False),
        sa.Column("reference_data_version", sa.String(40), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "rate_limit_buckets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scope", sa.String(40), nullable=False),
        sa.Column("bucket_key", sa.String(64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.UniqueConstraint("scope", "bucket_key", "window_start", name="uq_rate_limit_bucket"),
    )
    op.create_index("ix_rate_limit_buckets_scope", "rate_limit_buckets", ["scope"])
    op.create_index("ix_rate_limit_buckets_bucket_key", "rate_limit_buckets", ["bucket_key"])
    op.create_table(
        "patient_access_codes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_patient_access_codes_case_id", "patient_access_codes", ["case_id"])
    op.create_index("ix_patient_access_codes_code_hash", "patient_access_codes", ["code_hash"], unique=True)


def downgrade() -> None:
    for table, indexes in [
        ("patient_access_codes", ["ix_patient_access_codes_code_hash", "ix_patient_access_codes_case_id"]),
        ("rate_limit_buckets", ["ix_rate_limit_buckets_bucket_key", "ix_rate_limit_buckets_scope"]),
        ("benchmark_runs", []),
        ("processing_metrics", ["ix_processing_metrics_name", "ix_processing_metrics_case_id"]),
        ("integration_exports", ["ix_integration_exports_case_id"]),
        ("on_site_attestations", ["ix_on_site_attestations_case_id"]),
        ("review_decisions", ["ix_review_decisions_case_id"]),
        ("finding_overrides", ["ix_finding_overrides_finding_id", "ix_finding_overrides_case_id"]),
        ("override_requests", ["ix_override_requests_finding_id", "ix_override_requests_case_id"]),
        ("rule_findings", ["ix_rule_findings_evaluation_id"]),
        ("eligibility_evaluations", ["ix_eligibility_evaluations_stale", "ix_eligibility_evaluations_input_hash", "ix_eligibility_evaluations_case_id"]),
        ("staff_corrections", ["ix_staff_corrections_assertion_id", "ix_staff_corrections_case_id"]),
        ("field_assertions", ["ix_field_assertions_field_name", "ix_field_assertions_document_id", "ix_field_assertions_case_id"]),
        ("questionnaire_submissions", ["ix_questionnaire_submissions_case_id"]),
        ("patient_profiles", ["ix_patient_profiles_identity_hash", "ix_patient_profiles_case_id"]),
        ("billing_rules", ["ix_billing_rules_release_id"]),
        ("clinic_panel_rules", ["ix_clinic_panel_rules_clinic_id", "ix_clinic_panel_rules_release_id"]),
        ("package_procedures", ["ix_package_procedures_package_version_id"]),
        ("procedures", ["ix_procedures_release_id"]),
        ("package_versions", ["ix_package_versions_code", "ix_package_versions_release_id"]),
        ("eligibility_contracts", ["ix_eligibility_contracts_organisation_code", "ix_eligibility_contracts_release_id"]),
        ("payer_organisations", ["ix_payer_organisations_release_id"]),
        ("reference_data_releases", ["ix_reference_data_releases_active", "ix_reference_data_releases_version"]),
    ]:
        for index in indexes:
            op.drop_index(index, table_name=table)
        op.drop_table(table)
    op.drop_index("ix_audit_events_integrity_digest", table_name="audit_events")
    op.drop_column("audit_events", "integrity_digest")
    op.drop_column("audit_events", "previous_digest")
    op.drop_column("documents", "scan_status")
    op.drop_column("cases", "requested_services")
