"""Persist synthetic demo document bytes for free-tier restarts.

Revision ID: 0004_durable_document_content
Revises: 0003_live_queue_and_room
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_durable_document_content"
down_revision = "0003_live_queue_and_room"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("content", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "content")
