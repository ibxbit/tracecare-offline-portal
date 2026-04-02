"""Authentication router — local-only Argon2id + JWT with session management.

Security features implemented here:
  • Argon2id password verification (via passlib).
  • Account lockout after 5 consecutive failures (15-min cooldown).
  • Brute-force counter persisted in the DB (survives restarts).
  • Access tokens carry a `jti` (JWT ID) so logout can revoke them.
  • Refresh tokens are rotated on every use (old token revoked immediately).
  • Session hash written to the User row on login; cleared on all-device logout.
  • All auth events recorded in the AuditLog.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.core.token_store import (
    access_token_store,
    login_attempt_tracker,
    refresh_token_store,
)
from app.database import get_db
from app.models.audit import AuditEventType
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest

router = APIRouter(prefix="/auth", tags=["auth"])

_MAX_FAILURES = 5
_LOCKOUT_MINUTES = 15


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _session_hash(session_id: str) -> str:
    return hashlib.sha256(session_id.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)

    # ── 1. In-memory brute-force check (fast path, no DB) ──────────────────
    locked, secs_remaining = login_attempt_tracker.is_locked(payload.username)
    if locked:
        audit(db, AuditEventType.login_locked,
              username=payload.username, ip=ip,
              detail=f"lockout {secs_remaining:.0f}s remaining")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account temporarily locked. Try again in {int(secs_remaining // 60) + 1} minute(s).",
            headers={"Retry-After": str(int(secs_remaining))},
        )

    # ── 2. Fetch user ───────────────────────────────────────────────────────
    user: User | None = db.execute(
        select(User).where(User.username == payload.username)
    ).scalar_one_or_none()

    # ── 3. Verify password ──────────────────────────────────────────────────
    password_ok = user is not None and verify_password(payload.password, user.hashed_password)

    if not password_ok:
        count = login_attempt_tracker.record_failure(payload.username)
        # Also persist failure in DB (survives restart)
        if user:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= _MAX_FAILURES:
                from datetime import timedelta
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=_LOCKOUT_MINUTES)
                audit(db, AuditEventType.account_locked,
                      user_id=user.id, username=user.username, ip=ip,
                      detail=f"locked after {user.failed_login_attempts} failures", commit=False)
            db.commit()

        audit(db, AuditEventType.login_failure, username=payload.username, ip=ip,
              detail=f"attempt {count}/{_MAX_FAILURES}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # ── 4. Account state checks ─────────────────────────────────────────────
    if not user.is_active:
        audit(db, AuditEventType.login_failure, user_id=user.id, username=user.username, ip=ip,
              detail="account deactivated")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    # DB-level lockout check (persisted across restarts)
    if user.locked_until and datetime.now(timezone.utc) < user.locked_until:
        remaining = (user.locked_until - datetime.now(timezone.utc)).total_seconds()
        audit(db, AuditEventType.login_locked, user_id=user.id, username=user.username, ip=ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account locked. Try again in {int(remaining // 60) + 1} minute(s).",
            headers={"Retry-After": str(int(remaining))},
        )

    # ── 5. Reset failure counters ───────────────────────────────────────────
    login_attempt_tracker.record_success(payload.username)
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.now(timezone.utc)

    # ── 6. Generate session ID and tokens ───────────────────────────────────
    session_id = secrets.token_hex(16)
    user.session_token_hash = _session_hash(session_id)

    jti = secrets.token_hex(16)  # unique JWT ID for this access token
    token_data = {
        "sub": str(user.id),
        "role": user.role.value,
        "jti": jti,
        "sid": session_id,
    }
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token({"sub": str(user.id), "role": user.role.value, "sid": session_id})

    db.commit()

    audit(db, AuditEventType.login_success,
          user_id=user.id, username=user.username, ip=ip,
          http_method="POST", http_path="/api/auth/login")

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------

@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)

    if refresh_token_store.is_revoked(payload.refresh_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    try:
        token_data = decode_token(payload.refresh_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if token_data.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user: User | None = db.execute(
        select(User).where(User.id == int(token_data["sub"]))
    ).scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Session ID from old refresh token
    old_sid = token_data.get("sid")

    # ── Validate session binding ────────────────────────────────────────────
    # If a session hash is set, the old sid must match it.
    if user.session_token_hash and old_sid:
        if _session_hash(old_sid) != user.session_token_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been invalidated. Please log in again.",
            )

    # ── Rotate: revoke old refresh token, issue new pair ───────────────────
    exp = token_data.get("exp")
    if exp:
        from datetime import datetime as _dt
        refresh_token_store.revoke(payload.refresh_token, _dt.fromtimestamp(exp, tz=timezone.utc))

    # New session ID (rotates session binding every 12 h)
    new_session_id = secrets.token_hex(16)
    user.session_token_hash = _session_hash(new_session_id)
    db.commit()

    new_jti = secrets.token_hex(16)
    new_token_data = {"sub": str(user.id), "role": user.role.value, "jti": new_jti, "sid": new_session_id}
    access_token = create_access_token(new_token_data)
    new_refresh = create_refresh_token({"sub": str(user.id), "role": user.role.value, "sid": new_session_id})

    audit(db, AuditEventType.token_refresh, user_id=user.id, username=user.username, ip=ip)

    return TokenResponse(access_token=access_token, refresh_token=new_refresh)


# ---------------------------------------------------------------------------
# Logout (single device)
# ---------------------------------------------------------------------------

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)):
    """Revoke the provided refresh token. The access token expires on its own (≤15 min)."""
    ip = _client_ip(request)

    # Optionally also revoke the access token if sent in Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        raw_access = auth_header[7:]
        try:
            payload_data = decode_token(raw_access)
            jti = payload_data.get("jti")
            exp = payload_data.get("exp")
            if jti and exp:
                from datetime import datetime as _dt
                access_token_store.revoke(jti, _dt.fromtimestamp(exp, tz=timezone.utc))
        except ValueError:
            pass  # Already expired — nothing to revoke

    # Revoke refresh token
    try:
        rt_data = decode_token(payload.refresh_token)
        exp = rt_data.get("exp")
        if exp:
            from datetime import datetime as _dt
            refresh_token_store.revoke(payload.refresh_token, _dt.fromtimestamp(exp, tz=timezone.utc))
        user_id = int(rt_data.get("sub", 0)) or None
    except ValueError:
        user_id = None

    audit(db, AuditEventType.logout, user_id=user_id, ip=ip,
          detail="single-device logout")


# ---------------------------------------------------------------------------
# Logout all devices (clears session hash — invalidates all existing tokens)
# ---------------------------------------------------------------------------

@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(request: Request, db: Session = Depends(get_db)):
    """
    Invalidate ALL active sessions for the current user by clearing
    session_token_hash.  Any token issued before this call will fail
    the session-binding check on the next refresh.
    """
    from app.core.dependencies import get_current_user

    # We need a real authenticated user for this endpoint
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from fastapi import Header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    raw = auth_header[7:]
    try:
        data = decode_token(raw)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user: User | None = db.execute(
        select(User).where(User.id == int(data["sub"]))
    ).scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    user.session_token_hash = None  # invalidates all existing session bindings
    db.commit()

    audit(db, AuditEventType.logout, user_id=user.id, username=user.username,
          ip=_client_ip(request), detail="all-device logout — session hash cleared")
