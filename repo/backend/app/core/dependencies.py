"""FastAPI dependency providers for authentication and RBAC.

get_current_user:
  1. Extracts Bearer token from Authorization header.
  2. Verifies signature and expiry (via decode_token).
  3. Rejects tokens whose `jti` has been revoked (logout).
  4. Verifies session binding (`sid` claim matches session_token_hash in DB).
  5. Loads and returns the live User row.

require_role(*roles):
  Factory that returns a dependency enforcing one of the listed roles.
"""
from __future__ import annotations

import hashlib

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.security import decode_token
from app.core.token_store import access_token_store
from app.database import get_db
from app.models.user import User

bearer_scheme = HTTPBearer()


def _session_hash(session_id: str) -> str:
    return hashlib.sha256(session_id.encode()).hexdigest()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials

    # ── 1. Verify signature / expiry ──────────────────────────────────────
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    # ── 2. Check access token revocation (logout) ─────────────────────────
    jti = payload.get("jti")
    if jti and access_token_store.is_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please log in again.",
        )

    # ── 3. Resolve user ───────────────────────────────────────────────────
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )

    user = db.execute(
        select(User).where(User.id == int(user_id))
    ).scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # ── 4. Session binding check ──────────────────────────────────────────
    # If the user has an active session_token_hash, the `sid` claim in the
    # token must hash to the same value.  Clearing session_token_hash (logout-all)
    # invalidates all outstanding tokens.
    sid = payload.get("sid")
    if user.session_token_hash is not None:
        if sid is None or _session_hash(sid) != user.session_token_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session invalidated. Please log in again.",
            )

    return user


def require_role(*roles: str):
    """Return a dependency that requires the current user to have one of *roles*."""
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.value not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(roles)}",
            )
        return current_user
    return dependency
