from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets
from argon2 import PasswordHasher
from fastapi import Cookie, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import get_settings
from .db import get_db
from .models import StaffSession, User


ph = PasswordHasher()
settings = get_settings()


def hash_token(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def create_session(db: Session, user: User, response: Response) -> str:
    token = secrets.token_urlsafe(32)
    db.add(StaffSession(token_hash=hash_token(token), user_id=user.id, expires_at=datetime.now(timezone.utc) + timedelta(hours=8)))
    db.commit()
    response.set_cookie(
        "cp_staff",
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=8 * 3600,
        path="/",
    )
    return token


def current_staff(cp_staff: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> User:
    if not cp_staff:
        raise HTTPException(401, "Staff sign-in required")
    record = db.scalar(select(StaffSession).where(StaffSession.token_hash == hash_token(cp_staff)))
    if not record or record.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc) or not record.user.active:
        raise HTTPException(401, "Session expired")
    return record.user


def manager_only(user: User = Depends(current_staff)) -> User:
    if user.role != "manager":
        raise HTTPException(403, "Manager access required")
    return user
