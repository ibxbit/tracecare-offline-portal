"""Audit log query endpoints — admin only, read-only.

No deletion or modification endpoints exist by design:
the audit log is append-only at the application layer.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.database import get_db
from app.models.audit import AuditEventType, AuditLog
from app.models.user import User
from pydantic import BaseModel

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditLogResponse(BaseModel):
    id: int
    event_type: AuditEventType
    user_id: Optional[int]
    username: Optional[str]
    ip_address: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[str]
    detail: Optional[str]
    http_method: Optional[str]
    http_path: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[AuditLogResponse])
def list_audit_logs(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
    event_type: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    resource_type: Optional[str] = Query(None),
    ip_address: Optional[str] = Query(None),
    since: Optional[datetime] = Query(None, description="ISO-8601 UTC start time"),
    until: Optional[datetime] = Query(None, description="ISO-8601 UTC end time"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    q = select(AuditLog)

    if event_type:
        try:
            q = q.where(AuditLog.event_type == AuditEventType(event_type))
        except ValueError:
            pass
    if user_id is not None:
        q = q.where(AuditLog.user_id == user_id)
    if resource_type:
        q = q.where(AuditLog.resource_type == resource_type)
    if ip_address:
        q = q.where(AuditLog.ip_address == ip_address)
    if since:
        q = q.where(AuditLog.created_at >= since)
    if until:
        q = q.where(AuditLog.created_at <= until)

    logs = db.execute(
        q.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    ).scalars().all()
    return logs


@router.get("/{log_id}", response_model=AuditLogResponse)
def get_audit_log(
    log_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    from fastapi import HTTPException, status
    log = db.execute(select(AuditLog).where(AuditLog.id == log_id)).scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log entry not found")
    return log
