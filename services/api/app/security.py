from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import secrets
from typing import Any

from cryptography.fernet import Fernet
from fastapi import HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import AuditEvent, RateLimitBucket


settings = get_settings()


def _canonical_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(tzinfo=None).isoformat() if value.tzinfo else value.isoformat()


def _fernet() -> Fernet:
    configured = settings.encryption_key.strip().encode()
    if configured:
        return Fernet(configured)
    derived = base64.urlsafe_b64encode(hashlib.sha256(settings.session_secret.encode()).digest())
    return Fernet(derived)


def encrypt_identity(value: str) -> str:
    return _fernet().encrypt(value.strip().upper().encode()).decode()


def identity_hash(value: str) -> str:
    return hmac.new(settings.identity_hmac_key.encode(), value.strip().upper().encode(), hashlib.sha256).hexdigest()


def mask_identity(value: str) -> str:
    normalized = value.strip().upper()
    return f"••••{normalized[-4:]}"


def append_audit(
    db: Session,
    case_id: str | None,
    actor_type: str,
    actor_id: str | None,
    action: str,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    previous = db.scalar(select(AuditEvent).order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(1))
    previous_digest = previous.integrity_digest if previous else None
    created_at = datetime.now(timezone.utc)
    safe_details = details or {}
    canonical = json.dumps(
        {
            "previous_digest": previous_digest,
            "case_id": case_id,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "action": action,
            "details": safe_details,
            "created_at": _canonical_time(created_at),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hmac.new(settings.session_secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    event = AuditEvent(
        case_id=case_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        details=safe_details,
        created_at=created_at,
        previous_digest=previous_digest,
        integrity_digest=digest,
    )
    db.add(event)
    return event


def verify_audit_chain(events: list[AuditEvent]) -> bool:
    previous_digest: str | None = None
    for event in events:
        canonical = json.dumps(
            {
                "previous_digest": previous_digest,
                "case_id": event.case_id,
                "actor_type": event.actor_type,
                "actor_id": event.actor_id,
                "action": event.action,
                "details": event.details,
                "created_at": _canonical_time(event.created_at),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        expected = hmac.new(settings.session_secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        if event.previous_digest != previous_digest or not event.integrity_digest or not hmac.compare_digest(event.integrity_digest, expected):
            return False
        previous_digest = event.integrity_digest
    return True


def backfill_audit_chain(db: Session) -> None:
    previous_digest: str | None = None
    events = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at, AuditEvent.id)).all()
    for event in events:
        canonical = json.dumps(
            {
                "previous_digest": previous_digest,
                "case_id": event.case_id,
                "actor_type": event.actor_type,
                "actor_id": event.actor_id,
                "action": event.action,
                "details": event.details,
                "created_at": _canonical_time(event.created_at),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        event.previous_digest = previous_digest
        event.integrity_digest = hmac.new(settings.session_secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        previous_digest = event.integrity_digest
    db.flush()


def issue_csrf(response: Response, session_token: str) -> str:
    nonce = secrets.token_urlsafe(24)
    signature = hmac.new(settings.session_secret.encode(), f"{session_token}:{nonce}".encode(), hashlib.sha256).hexdigest()
    token = f"{nonce}.{signature}"
    response.set_cookie(
        "cp_csrf",
        token,
        httponly=False,
        samesite="strict",
        secure=settings.cookie_secure,
        max_age=8 * 3600,
        path="/",
    )
    return token


def verify_csrf(request: Request) -> None:
    if not settings.csrf_enabled or request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    session_token = request.cookies.get("cp_staff")
    if not session_token:
        return
    cookie_token = request.cookies.get("cp_csrf", "")
    header_token = request.headers.get("x-csrf-token", "")
    if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
        raise HTTPException(403, "CSRF validation failed")
    try:
        nonce, signature = cookie_token.rsplit(".", 1)
    except ValueError as exc:
        raise HTTPException(403, "CSRF validation failed") from exc
    expected = hmac.new(settings.session_secret.encode(), f"{session_token}:{nonce}".encode(), hashlib.sha256).hexdigest()
    if not secrets.compare_digest(signature, expected):
        raise HTTPException(403, "CSRF validation failed")
    origin = request.headers.get("origin")
    if origin:
        forwarded_host = request.headers.get("x-forwarded-host") or request.url.netloc
        if origin.split("://", 1)[-1].rstrip("/") != forwarded_host:
            raise HTTPException(403, "Request origin is not allowed")


def rate_limit(db: Session, scope: str, key: str, limit: int, window_seconds: int) -> None:
    now = datetime.now(timezone.utc)
    epoch = int(now.timestamp())
    start = datetime.fromtimestamp(epoch - (epoch % window_seconds), tz=timezone.utc)
    key_hash = hmac.new(settings.session_secret.encode(), key.encode(), hashlib.sha256).hexdigest()
    bucket = db.scalar(select(RateLimitBucket).where(
        RateLimitBucket.scope == scope,
        RateLimitBucket.bucket_key == key_hash,
        RateLimitBucket.window_start == start,
    ))
    if not bucket:
        bucket = RateLimitBucket(scope=scope, bucket_key=key_hash, window_start=start, count=0)
        db.add(bucket)
        db.flush()
    if bucket.count >= limit:
        retry_after = max(1, int((start + timedelta(seconds=window_seconds) - now).total_seconds()))
        raise HTTPException(429, "Too many requests", headers={"Retry-After": str(retry_after)})
    bucket.count += 1


class UploadScanner:
    name = "interface"

    def scan(self, content: bytes, filename: str, media_type: str) -> tuple[bool, str]:
        raise NotImplementedError


class DeterministicDemoScanner(UploadScanner):
    """Clearly labelled local scanner for synthetic demos; production must replace it."""

    name = "deterministic_demo"

    def scan(self, content: bytes, filename: str, media_type: str) -> tuple[bool, str]:
        del filename, media_type
        if b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in content:
            return False, "Known antivirus test signature detected"
        return True, "Synthetic demo scanner passed"


def get_upload_scanner() -> UploadScanner:
    if settings.upload_scanner == "deterministic_demo":
        return DeterministicDemoScanner()
    raise RuntimeError(f"Upload scanner '{settings.upload_scanner}' is not configured")
