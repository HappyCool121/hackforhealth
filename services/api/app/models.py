from __future__ import annotations
from datetime import date, datetime, timezone
from uuid import uuid4
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


def uid() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(30))
    clinic_id: Mapped[str] = mapped_column(String(50), default="clinic-central")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class StaffSession(Base):
    __tablename__ = "staff_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship()


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    reference: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    patient_name: Mapped[str] = mapped_column(String(150))
    patient_email: Mapped[str] = mapped_column(String(255))
    id_last4: Mapped[str] = mapped_column(String(4))
    appointment_type: Mapped[str] = mapped_column(String(20))
    appointment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    visit_reason: Mapped[str] = mapped_column(String(50), default="other_unsure")
    document_requirement: Mapped[str] = mapped_column(String(10), default="yes")
    identity_source: Mapped[str] = mapped_column(String(30), default="manual")
    clinic_id: Mapped[str] = mapped_column(String(50), default="clinic-central")
    status: Mapped[str] = mapped_column(String(40), default="DRAFT", index=True)
    patient_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    rules: Mapped[list] = mapped_column(JSON, default=list)
    ai_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    check_in_confirmations: Mapped[dict] = mapped_column(JSON, default=dict)
    queue_number: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True, index=True)
    queue_status: Mapped[str] = mapped_column(String(30), default="NOT_ISSUED")
    room_assignment: Mapped[str | None] = mapped_column(String(80), nullable=True)
    queue_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    documents: Mapped[list[Document]] = relationship(back_populates="case", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    expected_category: Mapped[str] = mapped_column(String(40))
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(100))
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="QUEUED")
    processing_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    extracted_data: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    quality_warnings: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    case: Mapped[Case] = relationship(back_populates="documents")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReferenceData(Base):
    __tablename__ = "reference_data"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    code: Mapped[str] = mapped_column(String(60))
    label: Mapped[str] = mapped_column(String(150))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
