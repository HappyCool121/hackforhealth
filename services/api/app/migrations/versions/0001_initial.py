"""Initial ClinicPass schema.

Revision ID: 0001_initial
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("clinic_id", sa.String(length=50), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "cases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reference", sa.String(length=24), nullable=False),
        sa.Column("patient_name", sa.String(length=150), nullable=False),
        sa.Column("patient_email", sa.String(length=255), nullable=False),
        sa.Column("id_last4", sa.String(length=4), nullable=False),
        sa.Column("appointment_type", sa.String(length=20), nullable=False),
        sa.Column("appointment_date", sa.Date(), nullable=True),
        sa.Column("clinic_id", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("patient_token_hash", sa.String(length=64), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("ai_provider", sa.String(length=30), nullable=True),
        sa.Column("check_in_confirmations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cases_patient_token_hash", "cases", ["patient_token_hash"], unique=True)
    op.create_index("ix_cases_reference", "cases", ["reference"], unique=True)
    op.create_index("ix_cases_status", "cases", ["status"], unique=False)

    op.create_table(
        "reference_data",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("label", sa.String(length=150), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reference_data_kind", "reference_data", ["kind"], unique=False)

    op.create_table(
        "staff_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_staff_sessions_token_hash", "staff_sessions", ["token_hash"], unique=True)

    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("expected_category", sa.String(length=40), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("extracted_data", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("quality_warnings", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_case_id", "documents", ["case_id"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=True),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=100), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_case_id", "audit_events", ["case_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_events_case_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_documents_case_id", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_staff_sessions_token_hash", table_name="staff_sessions")
    op.drop_table("staff_sessions")
    op.drop_index("ix_reference_data_kind", table_name="reference_data")
    op.drop_table("reference_data")
    op.drop_index("ix_cases_status", table_name="cases")
    op.drop_index("ix_cases_reference", table_name="cases")
    op.drop_index("ix_cases_patient_token_hash", table_name="cases")
    op.drop_table("cases")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
