"""Add patient intake declarations and document processing metadata.

Revision ID: 0002_patient_intake_and_vision
Revises: 0001_initial
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_patient_intake_and_vision"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cases",
        sa.Column("visit_reason", sa.String(length=50), nullable=False, server_default="other_unsure"),
    )
    op.add_column(
        "cases",
        sa.Column("document_requirement", sa.String(length=10), nullable=False, server_default="yes"),
    )
    op.add_column(
        "cases",
        sa.Column("identity_source", sa.String(length=30), nullable=False, server_default="manual"),
    )
    op.add_column(
        "documents",
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("documents", sa.Column("sha256", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("processing_provider", sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "processing_provider")
    op.drop_column("documents", "sha256")
    op.drop_column("documents", "page_count")
    op.drop_column("cases", "identity_source")
    op.drop_column("cases", "document_requirement")
    op.drop_column("cases", "visit_reason")
