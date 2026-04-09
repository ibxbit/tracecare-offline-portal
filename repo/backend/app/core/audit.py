"""Audit event recorder — thin helper used throughout the application.

Usage:
    from app.core.audit import audit

    audit(db, AuditEventType.login_success,
          user_id=user.id, username=user.username,
          ip=client_ip, detail="via /api/auth/login")
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.audit import AuditEventType, AuditLog


def audit(
    db: Session,
    event_type: AuditEventType,
    *,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    ip: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    detail: Optional[str] = None,
    http_method: Optional[str] = None,
    http_path: Optional[str] = None,
    commit: bool = True,
) -> AuditLog:
    """
    Insert an immutable audit row.

    *commit=True* is the default so callers don't need to worry about
    flushing. Pass *commit=False* inside a multi-step transaction where
    the outer code owns the commit.
    """
    log = AuditLog(
        event_type=event_type,
        user_id=user_id,
        username=username,
        ip_address=ip,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        detail=detail,
        http_method=http_method,
        http_path=http_path,
    )
    db.add(log)
    if commit:
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
    return log
