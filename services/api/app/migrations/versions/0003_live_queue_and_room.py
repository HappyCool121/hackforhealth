"""Add patient-visible queue and room updates.

Revision ID: 0003_live_queue_and_room
Revises: 0002_patient_intake_and_vision
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_live_queue_and_room"
down_revision = "0002_patient_intake_and_vision"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("queue_number", sa.String(length=20), nullable=True))
    op.add_column(
        "cases",
        sa.Column("queue_status", sa.String(length=30), nullable=False, server_default="NOT_ISSUED"),
    )
    op.add_column("cases", sa.Column("room_assignment", sa.String(length=80), nullable=True))
    op.add_column("cases", sa.Column("queue_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_cases_queue_number", "cases", ["queue_number"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_cases_queue_number", table_name="cases")
    op.drop_column("cases", "queue_updated_at")
    op.drop_column("cases", "room_assignment")
    op.drop_column("cases", "queue_status")
    op.drop_column("cases", "queue_number")
