"""Admin Console router.

Covers:
  - Site rule management
  - System parameters
  - Admin task management (internal + external on-prem trigger)
  - Proxy pool (internal network only)
  - API key management with per-key rate limits (60 req/min default)
  - Data export (CSV) for users, tasks, site rules
  - System status

Security model:
  - All /admin/* routes require JWT + admin role, EXCEPT the /admin/external/* routes
    which authenticate via X-Api-Key header (machine-to-machine for on-prem systems).
  - Rate limiting is enforced per API key using an in-memory sliding-window counter.
  - Proxy passwords are Fernet-encrypted at rest; never returned in responses.
"""
from __future__ import annotations

import csv
import hashlib
import io
import ipaddress
import json
import secrets
import socket
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.core.encryption import encryptor
from app.core.rate_limiter import check_rate_limit, current_usage, reset_key
from app.database import get_db
from app.models.admin import (
    AdminTask, ApiKey, ProxyPoolEntry, SiteRule, SystemParameter, TaskStatus,
)
from app.models.user import User
from app.schemas.admin import (
    AdminTaskBrief,
    AdminTaskCreate,
    AdminTaskResponse,
    AdminTaskStatusUpdate,
    ApiKeyCreate,
    ApiKeyCreatedResponse,
    ApiKeyResponse,
    ApiKeyUpdate,
    ExternalTaskCreate,
    ProxyHealthResult,
    ProxyPoolCreate,
    ProxyPoolResponse,
    ProxyPoolUpdate,
    SiteRuleCreate,
    SiteRuleResponse,
    SiteRuleUpdate,
    SystemParameterResponse,
    SystemParameterUpdate,
    SystemStatusResponse,
)

router = APIRouter(prefix="/admin", tags=["admin"])

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _raw_key_to_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _generate_api_key() -> tuple[str, str, str]:
    """Return (raw_key, key_hash, key_prefix)."""
    raw = "tc_" + secrets.token_urlsafe(32)
    hashed = _raw_key_to_hash(raw)
    prefix = raw[:12]
    return raw, hashed, prefix


def _ip_in_allowlist(client_ip: str, allowed_ips: str) -> bool:
    """Check whether *client_ip* falls within any entry in the comma-separated *allowed_ips*."""
    try:
        client = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    for entry in (e.strip() for e in allowed_ips.split(",") if e.strip()):
        try:
            if "/" in entry:
                if client in ipaddress.ip_network(entry, strict=False):
                    return True
            else:
                if client == ipaddress.ip_address(entry):
                    return True
        except ValueError:
            continue
    return False


# ---------------------------------------------------------------------------
# API-key authentication dependency (for external on-prem endpoints)
# ---------------------------------------------------------------------------

def _get_api_key(
    request: Request,
    x_api_key: str = Header(..., alias="X-Api-Key"),
    db: Session = Depends(get_db),
) -> ApiKey:
    key_hash = _raw_key_to_hash(x_api_key)
    api_key = db.execute(
        select(ApiKey).where(
            and_(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
        )
    ).scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key",
        )

    now = datetime.now(timezone.utc)
    if api_key.expires_at and now > api_key.expires_at:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired",
        )

    # IP allowlist enforcement
    if api_key.allowed_ips:
        client_ip = request.client.host if request.client else ""
        if not _ip_in_allowlist(client_ip, api_key.allowed_ips):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Client IP not in API key allowlist",
            )

    # Per-key sliding-window rate limit
    if not check_rate_limit(api_key.key_hash, api_key.rate_limit_per_minute, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded ({api_key.rate_limit_per_minute} req/min)",
            headers={"Retry-After": "60"},
        )

    # Update usage stats (best-effort; don't fail the request on error)
    try:
        api_key.last_used_at = now
        api_key.usage_count += 1
        db.commit()
    except Exception:
        db.rollback()

    return api_key


# ---------------------------------------------------------------------------
# Site Rules
# ---------------------------------------------------------------------------

@router.post("/rules", response_model=SiteRuleResponse, status_code=status.HTTP_201_CREATED)
def create_rule(
    payload: SiteRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    existing = db.execute(select(SiteRule).where(SiteRule.name == payload.name)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Site rule '{payload.name}' already exists",
        )
    rule = SiteRule(
        name=payload.name,
        value=payload.value,
        value_type=payload.value_type,
        description=payload.description,
        is_active=payload.is_active,
        created_by=current_user.id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/rules", response_model=list[SiteRuleResponse])
def list_rules(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
    active_only: bool = Query(False),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    q = select(SiteRule)
    if active_only:
        q = q.where(SiteRule.is_active == True)
    if search:
        term = f"%{search}%"
        q = q.where(or_(SiteRule.name.ilike(term), SiteRule.description.ilike(term)))
    rules = db.execute(q.order_by(SiteRule.name).offset(skip).limit(limit)).scalars().all()
    return rules


@router.get("/rules/{rule_id}", response_model=SiteRuleResponse)
def get_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    rule = db.execute(select(SiteRule).where(SiteRule.id == rule_id)).scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site rule not found")
    return rule


@router.put("/rules/{rule_id}", response_model=SiteRuleResponse)
def update_rule(
    rule_id: int,
    payload: SiteRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    rule = db.execute(select(SiteRule).where(SiteRule.id == rule_id)).scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site rule not found")
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No fields to update")
    for field, value in updates.items():
        setattr(rule, field, value)
    rule.updated_by = current_user.id
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/rules/{rule_id}/toggle", response_model=SiteRuleResponse)
def toggle_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    rule = db.execute(select(SiteRule).where(SiteRule.id == rule_id)).scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site rule not found")
    rule.is_active = not rule.is_active
    rule.updated_by = current_user.id
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    rule = db.execute(select(SiteRule).where(SiteRule.id == rule_id)).scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site rule not found")
    db.delete(rule)
    db.commit()


# ---------------------------------------------------------------------------
# System Parameters
# ---------------------------------------------------------------------------

@router.get("/parameters", response_model=list[SystemParameterResponse])
def list_parameters(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
):
    params = db.execute(
        select(SystemParameter).order_by(SystemParameter.key).offset(skip).limit(limit)
    ).scalars().all()
    return params


@router.get("/parameters/{key}", response_model=SystemParameterResponse)
def get_parameter(
    key: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    param = db.execute(
        select(SystemParameter).where(SystemParameter.key == key)
    ).scalar_one_or_none()
    if not param:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parameter not found")
    return param


@router.put("/parameters/{key}", response_model=SystemParameterResponse)
def update_parameter(
    key: str,
    payload: SystemParameterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    param = db.execute(
        select(SystemParameter).where(SystemParameter.key == key)
    ).scalar_one_or_none()
    if not param:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parameter not found")
    if param.is_readonly:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Parameter '{key}' is read-only",
        )
    param.value = payload.value
    if payload.description is not None:
        param.description = payload.description
    param.updated_by = current_user.id
    db.commit()
    db.refresh(param)
    return param


# ---------------------------------------------------------------------------
# Admin Tasks (internal)
# ---------------------------------------------------------------------------

@router.post("/tasks", response_model=AdminTaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: AdminTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "clinic_staff")),
):
    task = AdminTask(
        name=payload.name,
        task_type=payload.task_type,
        priority=payload.priority,
        payload_json=payload.payload_json,
        assigned_to=payload.assigned_to,
        scheduled_at=payload.scheduled_at,
        created_by=current_user.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/tasks", response_model=list[AdminTaskBrief])
def list_tasks(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin", "clinic_staff")),
    task_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    external_system: Optional[str] = Query(None),
    assigned_to: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    q = select(AdminTask)
    if task_type:
        q = q.where(AdminTask.task_type == task_type)
    if status_filter:
        try:
            q = q.where(AdminTask.status == TaskStatus(status_filter))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status '{status_filter}'")
    if external_system:
        q = q.where(AdminTask.external_system == external_system)
    if assigned_to is not None:
        q = q.where(AdminTask.assigned_to == assigned_to)
    tasks = db.execute(
        q.order_by(AdminTask.priority.desc(), AdminTask.created_at.desc()).offset(skip).limit(limit)
    ).scalars().all()
    return tasks


@router.get("/tasks/{task_id}", response_model=AdminTaskResponse)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin", "clinic_staff")),
):
    task = db.execute(select(AdminTask).where(AdminTask.id == task_id)).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.patch("/tasks/{task_id}/status", response_model=AdminTaskResponse)
def update_task_status(
    task_id: int,
    payload: AdminTaskStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    task = db.execute(select(AdminTask).where(AdminTask.id == task_id)).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if task.status in (TaskStatus.completed, TaskStatus.cancelled):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot update a {task.status.value} task",
        )

    now = datetime.now(timezone.utc)
    task.status = payload.status
    if payload.status == TaskStatus.running and task.started_at is None:
        task.started_at = now
    if payload.status in (TaskStatus.completed, TaskStatus.failed, TaskStatus.cancelled):
        task.completed_at = now
    if payload.result_json:
        task.result_json = payload.result_json
    if payload.error_message:
        task.error_message = payload.error_message

    db.commit()
    db.refresh(task)
    return task


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_task(
    task_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    task = db.execute(select(AdminTask).where(AdminTask.id == task_id)).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if task.status in (TaskStatus.completed, TaskStatus.cancelled):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task is already {task.status.value}",
        )
    task.status = TaskStatus.cancelled
    task.completed_at = datetime.now(timezone.utc)
    db.commit()


# ---------------------------------------------------------------------------
# External on-prem task endpoints (API-key auth, rate-limited)
# ---------------------------------------------------------------------------

@router.post(
    "/external/tasks",
    response_model=AdminTaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="External — trigger a task (API key required)",
)
def external_create_task(
    payload: ExternalTaskCreate,
    api_key: ApiKey = Depends(_get_api_key),
    db: Session = Depends(get_db),
):
    task = AdminTask(
        name=payload.name,
        task_type=payload.task_type,
        priority=payload.priority,
        payload_json=payload.payload_json,
        external_system=api_key.system_name,
        external_ref=payload.external_ref,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get(
    "/external/tasks/{task_id}",
    response_model=AdminTaskResponse,
    summary="External — query task status (API key required)",
)
def external_get_task(
    task_id: int,
    api_key: ApiKey = Depends(_get_api_key),
    db: Session = Depends(get_db),
):
    task = db.execute(
        select(AdminTask).where(
            and_(
                AdminTask.id == task_id,
                AdminTask.external_system == api_key.system_name,
            )
        )
    ).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.get(
    "/external/tasks",
    response_model=list[AdminTaskBrief],
    summary="External — list own tasks (API key required)",
)
def external_list_tasks(
    api_key: ApiKey = Depends(_get_api_key),
    db: Session = Depends(get_db),
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    q = select(AdminTask).where(AdminTask.external_system == api_key.system_name)
    if status_filter:
        try:
            q = q.where(AdminTask.status == TaskStatus(status_filter))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status '{status_filter}'")
    tasks = db.execute(
        q.order_by(AdminTask.created_at.desc()).offset(skip).limit(limit)
    ).scalars().all()
    return tasks


# ---------------------------------------------------------------------------
# Proxy Pool
# ---------------------------------------------------------------------------

@router.post("/proxy-pool", response_model=ProxyPoolResponse, status_code=status.HTTP_201_CREATED)
def create_proxy(
    payload: ProxyPoolCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    password_encrypted = None
    if payload.password:
        password_encrypted = encryptor.encrypt(payload.password)

    entry = ProxyPoolEntry(
        label=payload.label,
        host=payload.host,
        port=payload.port,
        protocol=payload.protocol,
        username=payload.username,
        password_encrypted=password_encrypted,
        is_active=payload.is_active,
        weight=payload.weight,
        region=payload.region,
        created_by=current_user.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/proxy-pool", response_model=list[ProxyPoolResponse])
def list_proxies(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
    active_only: bool = Query(False),
    region: Optional[str] = Query(None),
    protocol: Optional[str] = Query(None),
):
    q = select(ProxyPoolEntry)
    if active_only:
        q = q.where(ProxyPoolEntry.is_active == True)
    if region:
        q = q.where(ProxyPoolEntry.region == region)
    if protocol:
        q = q.where(ProxyPoolEntry.protocol == protocol)
    entries = db.execute(
        q.order_by(ProxyPoolEntry.weight.desc(), ProxyPoolEntry.label)
    ).scalars().all()
    return entries


@router.get("/proxy-pool/{proxy_id}", response_model=ProxyPoolResponse)
def get_proxy(
    proxy_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    entry = db.execute(
        select(ProxyPoolEntry).where(ProxyPoolEntry.id == proxy_id)
    ).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy entry not found")
    return entry


@router.put("/proxy-pool/{proxy_id}", response_model=ProxyPoolResponse)
def update_proxy(
    proxy_id: int,
    payload: ProxyPoolUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    entry = db.execute(
        select(ProxyPoolEntry).where(ProxyPoolEntry.id == proxy_id)
    ).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy entry not found")

    updates = payload.model_dump(exclude_none=True, exclude={"password"})
    for field, value in updates.items():
        setattr(entry, field, value)

    if payload.password is not None:
        entry.password_encrypted = encryptor.encrypt(payload.password) if payload.password else None

    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/proxy-pool/{proxy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_proxy(
    proxy_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    entry = db.execute(
        select(ProxyPoolEntry).where(ProxyPoolEntry.id == proxy_id)
    ).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy entry not found")
    db.delete(entry)
    db.commit()


@router.patch("/proxy-pool/{proxy_id}/health-check", response_model=ProxyHealthResult)
def health_check_proxy(
    proxy_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """Attempt a TCP connection to the proxy host:port to verify reachability."""
    entry = db.execute(
        select(ProxyPoolEntry).where(ProxyPoolEntry.id == proxy_id)
    ).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy entry not found")

    now = datetime.now(timezone.utc)
    is_healthy = False
    detail = ""
    try:
        sock = socket.create_connection((entry.host, entry.port), timeout=5)
        sock.close()
        is_healthy = True
        detail = "TCP connection succeeded"
    except OSError as exc:
        detail = f"TCP connection failed: {exc}"

    entry.is_healthy = is_healthy
    entry.last_checked_at = now
    db.commit()

    return ProxyHealthResult(
        id=entry.id,
        host=entry.host,
        port=entry.port,
        is_healthy=is_healthy,
        checked_at=now,
        detail=detail,
    )


# ---------------------------------------------------------------------------
# API Key management
# ---------------------------------------------------------------------------

@router.post("/api-keys", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_api_key(
    payload: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    raw, key_hash, key_prefix = _generate_api_key()
    api_key = ApiKey(
        label=payload.label,
        system_name=payload.system_name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        rate_limit_per_minute=payload.rate_limit_per_minute,
        allowed_ips=payload.allowed_ips,
        expires_at=payload.expires_at,
        created_by=current_user.id,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return ApiKeyCreatedResponse(
        **ApiKeyResponse.model_validate(api_key).model_dump(),
        raw_key=raw,
    )


@router.get("/api-keys", response_model=list[ApiKeyResponse])
def list_api_keys(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
    active_only: bool = Query(False),
    system_name: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    q = select(ApiKey)
    if active_only:
        q = q.where(ApiKey.is_active == True)
    if system_name:
        q = q.where(ApiKey.system_name == system_name)
    keys = db.execute(
        q.order_by(ApiKey.system_name, ApiKey.created_at.desc()).offset(skip).limit(limit)
    ).scalars().all()
    return keys


@router.get("/api-keys/{key_id}", response_model=ApiKeyResponse)
def get_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    api_key = db.execute(select(ApiKey).where(ApiKey.id == key_id)).scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    return api_key


@router.put("/api-keys/{key_id}", response_model=ApiKeyResponse)
def update_api_key(
    key_id: int,
    payload: ApiKeyUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    api_key = db.execute(select(ApiKey).where(ApiKey.id == key_id)).scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No fields to update")
    for field, value in updates.items():
        setattr(api_key, field, value)
    db.commit()
    db.refresh(api_key)
    return api_key


@router.patch("/api-keys/{key_id}/rotate", response_model=ApiKeyCreatedResponse)
def rotate_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """Issue a new secret for the key. The old secret is immediately invalidated."""
    api_key = db.execute(select(ApiKey).where(ApiKey.id == key_id)).scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    old_hash = api_key.key_hash
    raw, key_hash, key_prefix = _generate_api_key()
    api_key.key_hash = key_hash
    api_key.key_prefix = key_prefix
    api_key.usage_count = 0
    api_key.last_used_at = None
    db.commit()
    db.refresh(api_key)

    # Evict old hash from rate-limiter window
    reset_key(old_hash)

    return ApiKeyCreatedResponse(
        **ApiKeyResponse.model_validate(api_key).model_dump(),
        raw_key=raw,
    )


@router.patch("/api-keys/{key_id}/toggle", response_model=ApiKeyResponse)
def toggle_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    api_key = db.execute(select(ApiKey).where(ApiKey.id == key_id)).scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    api_key.is_active = not api_key.is_active
    db.commit()
    db.refresh(api_key)
    return api_key


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    api_key = db.execute(select(ApiKey).where(ApiKey.id == key_id)).scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    reset_key(api_key.key_hash)
    db.delete(api_key)
    db.commit()


# ---------------------------------------------------------------------------
# CSV Data Exports
# ---------------------------------------------------------------------------

def _stream_csv(rows: list[dict], filename: str) -> StreamingResponse:
    if not rows:
        output = ""
    else:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        output = buf.getvalue()
    return StreamingResponse(
        iter([output]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/site-rules")
def export_site_rules(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
    active_only: bool = Query(False),
):
    q = select(SiteRule)
    if active_only:
        q = q.where(SiteRule.is_active == True)
    rules = db.execute(q.order_by(SiteRule.name)).scalars().all()
    rows = [
        {
            "id": r.id,
            "name": r.name,
            "value": r.value,
            "value_type": r.value_type.value,
            "description": r.description or "",
            "is_active": r.is_active,
            "created_by": r.created_by,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
        }
        for r in rules
    ]
    return _stream_csv(rows, "site_rules.csv")


@router.get("/export/tasks")
def export_tasks(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
    status_filter: Optional[str] = Query(None, alias="status"),
    task_type: Optional[str] = Query(None),
):
    q = select(AdminTask)
    if status_filter:
        try:
            q = q.where(AdminTask.status == TaskStatus(status_filter))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status '{status_filter}'")
    if task_type:
        q = q.where(AdminTask.task_type == task_type)
    tasks = db.execute(q.order_by(AdminTask.created_at.desc())).scalars().all()
    rows = [
        {
            "id": t.id,
            "name": t.name,
            "task_type": t.task_type,
            "status": t.status.value,
            "priority": t.priority,
            "external_system": t.external_system or "",
            "external_ref": t.external_ref or "",
            "created_by": t.created_by or "",
            "assigned_to": t.assigned_to or "",
            "scheduled_at": t.scheduled_at.isoformat() if t.scheduled_at else "",
            "started_at": t.started_at.isoformat() if t.started_at else "",
            "completed_at": t.completed_at.isoformat() if t.completed_at else "",
            "created_at": t.created_at.isoformat(),
            "updated_at": t.updated_at.isoformat(),
            "error_message": t.error_message or "",
        }
        for t in tasks
    ]
    return _stream_csv(rows, "admin_tasks.csv")


@router.get("/export/users")
def export_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    from app.models.user import User as UserModel
    users = db.execute(
        select(UserModel).order_by(UserModel.id)
    ).scalars().all()
    rows = [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role.value,
            "is_active": u.is_active,
            "last_login": u.last_login.isoformat() if u.last_login else "",
            "failed_login_attempts": u.failed_login_attempts,
            "locked_until": u.locked_until.isoformat() if u.locked_until else "",
            "created_at": u.created_at.isoformat(),
            "updated_at": u.updated_at.isoformat(),
        }
        for u in users
    ]
    return _stream_csv(rows, "users.csv")


@router.get("/export/api-keys")
def export_api_keys(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """Export API key metadata (never exports the hash or raw key)."""
    keys = db.execute(select(ApiKey).order_by(ApiKey.system_name)).scalars().all()
    rows = [
        {
            "id": k.id,
            "label": k.label,
            "system_name": k.system_name,
            "key_prefix": k.key_prefix,
            "rate_limit_per_minute": k.rate_limit_per_minute,
            "allowed_ips": k.allowed_ips or "",
            "is_active": k.is_active,
            "usage_count": k.usage_count,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else "",
            "created_by": k.created_by,
            "created_at": k.created_at.isoformat(),
            "expires_at": k.expires_at.isoformat() if k.expires_at else "",
        }
        for k in keys
    ]
    return _stream_csv(rows, "api_keys.csv")


# ---------------------------------------------------------------------------
# System status
# ---------------------------------------------------------------------------

@router.get("/system/status", response_model=SystemStatusResponse)
def system_status(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    db_status = "ok"
    try:
        db.execute(select(func.now()))
    except Exception as exc:
        db_status = f"error: {exc}"

    pending_count = db.execute(
        select(func.count()).select_from(AdminTask).where(AdminTask.status == TaskStatus.pending)
    ).scalar_one()
    running_count = db.execute(
        select(func.count()).select_from(AdminTask).where(AdminTask.status == TaskStatus.running)
    ).scalar_one()
    active_keys = db.execute(
        select(func.count()).select_from(ApiKey).where(ApiKey.is_active == True)
    ).scalar_one()
    active_proxies = db.execute(
        select(func.count()).select_from(ProxyPoolEntry).where(ProxyPoolEntry.is_active == True)
    ).scalar_one()
    rules_count = db.execute(select(func.count()).select_from(SiteRule)).scalar_one()
    params_count = db.execute(select(func.count()).select_from(SystemParameter)).scalar_one()

    return SystemStatusResponse(
        status="ok" if db_status == "ok" else "degraded",
        database=db_status,
        active_tasks_pending=pending_count,
        active_tasks_running=running_count,
        active_api_keys=active_keys,
        active_proxies=active_proxies,
        site_rules_count=rules_count,
        system_parameters_count=params_count,
        timestamp=datetime.now(timezone.utc),
    )
