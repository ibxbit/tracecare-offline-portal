"""Pydantic schemas for the Admin Console module."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.admin import ProxyProtocol, TaskPriority, TaskStatus, ValueType


# ---------------------------------------------------------------------------
# Site Rules
# ---------------------------------------------------------------------------

class SiteRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=0, max_length=10_000)
    value_type: ValueType = ValueType.string
    description: Optional[str] = Field(default=None, max_length=2000)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        import re
        if not re.match(r"^[a-z][a-z0-9_]*$", v):
            raise ValueError("Rule name must be snake_case (lowercase letters, digits, underscores)")
        return v


class SiteRuleUpdate(BaseModel):
    value: Optional[str] = Field(default=None, max_length=10_000)
    value_type: Optional[ValueType] = None
    description: Optional[str] = Field(default=None, max_length=2000)
    is_active: Optional[bool] = None


class SiteRuleResponse(BaseModel):
    id: int
    name: str
    value: str
    value_type: ValueType
    description: Optional[str]
    is_active: bool
    created_by: int
    updated_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# System Parameters
# ---------------------------------------------------------------------------

class SystemParameterUpdate(BaseModel):
    value: str = Field(min_length=0, max_length=10_000)
    description: Optional[str] = Field(default=None, max_length=2000)


class SystemParameterResponse(BaseModel):
    id: int
    key: str
    value: str
    value_type: ValueType
    description: Optional[str]
    is_readonly: bool
    updated_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Admin Tasks
# ---------------------------------------------------------------------------

class AdminTaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    task_type: str = Field(min_length=1, max_length=100)
    priority: int = Field(default=5, ge=1, le=10)
    payload: Optional[dict[str, Any]] = None
    assigned_to: Optional[int] = None
    scheduled_at: Optional[datetime] = None

    @property
    def payload_json(self) -> Optional[str]:
        return json.dumps(self.payload) if self.payload is not None else None


class ExternalTaskCreate(BaseModel):
    """Payload sent by an external on-prem system to trigger a task."""
    name: str = Field(min_length=1, max_length=300)
    task_type: str = Field(min_length=1, max_length=100)
    priority: int = Field(default=5, ge=1, le=10)
    payload: Optional[dict[str, Any]] = None
    external_ref: Optional[str] = Field(default=None, max_length=200,
                                         description="Caller's own reference ID for correlation")

    @property
    def payload_json(self) -> Optional[str]:
        return json.dumps(self.payload) if self.payload is not None else None


class AdminTaskStatusUpdate(BaseModel):
    status: TaskStatus
    result: Optional[dict[str, Any]] = None
    error_message: Optional[str] = Field(default=None, max_length=5000)

    @property
    def result_json(self) -> Optional[str]:
        return json.dumps(self.result) if self.result is not None else None


class AdminTaskResponse(BaseModel):
    id: int
    name: str
    task_type: str
    status: TaskStatus
    priority: int
    payload_json: Optional[str]
    result_json: Optional[str]
    error_message: Optional[str]
    created_by: Optional[int]
    assigned_to: Optional[int]
    external_system: Optional[str]
    external_ref: Optional[str]
    scheduled_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @property
    def payload(self) -> Optional[dict]:
        return json.loads(self.payload_json) if self.payload_json else None

    @property
    def result(self) -> Optional[dict]:
        return json.loads(self.result_json) if self.result_json else None


class AdminTaskBrief(BaseModel):
    id: int
    name: str
    task_type: str
    status: TaskStatus
    priority: int
    external_system: Optional[str]
    external_ref: Optional[str]
    assigned_to: Optional[int]
    scheduled_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Proxy Pool
# ---------------------------------------------------------------------------

class ProxyPoolCreate(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    protocol: ProxyProtocol = ProxyProtocol.http
    username: Optional[str] = Field(default=None, max_length=200)
    password: Optional[str] = Field(default=None, max_length=500,
                                     description="Stored encrypted; never returned in responses")
    is_active: bool = True
    weight: int = Field(default=5, ge=1, le=10)
    region: Optional[str] = Field(default=None, max_length=100)


class ProxyPoolUpdate(BaseModel):
    label: Optional[str] = Field(default=None, max_length=200)
    host: Optional[str] = Field(default=None, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    protocol: Optional[ProxyProtocol] = None
    username: Optional[str] = Field(default=None, max_length=200)
    password: Optional[str] = Field(default=None, max_length=500)
    is_active: Optional[bool] = None
    weight: Optional[int] = Field(default=None, ge=1, le=10)
    region: Optional[str] = Field(default=None, max_length=100)


class ProxyPoolResponse(BaseModel):
    id: int
    label: str
    host: str
    port: int
    protocol: ProxyProtocol
    username: Optional[str]
    # password_encrypted is intentionally excluded
    is_active: bool
    weight: int
    region: Optional[str]
    last_checked_at: Optional[datetime]
    is_healthy: Optional[bool]
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProxyHealthResult(BaseModel):
    id: int
    host: str
    port: int
    is_healthy: bool
    checked_at: datetime
    detail: str


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------

class ApiKeyCreate(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    system_name: str = Field(min_length=1, max_length=200)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=6000)
    allowed_ips: Optional[str] = Field(
        default=None,
        description="Comma-separated IPs or CIDR ranges, e.g. '192.168.1.0/24,10.0.0.5'",
    )
    expires_at: Optional[datetime] = None


class ApiKeyResponse(BaseModel):
    id: int
    label: str
    system_name: str
    key_prefix: str
    rate_limit_per_minute: int
    allowed_ips: Optional[str]
    is_active: bool
    created_by: int
    last_used_at: Optional[datetime]
    usage_count: int
    created_at: datetime
    expires_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Returned only at creation and rotation — includes the raw key (shown once)."""
    raw_key: str


class ApiKeyUpdate(BaseModel):
    label: Optional[str] = Field(default=None, max_length=200)
    rate_limit_per_minute: Optional[int] = Field(default=None, ge=1, le=6000)
    allowed_ips: Optional[str] = None
    expires_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# System status
# ---------------------------------------------------------------------------

class SystemStatusResponse(BaseModel):
    status: str = "ok"
    database: str
    active_tasks_pending: int
    active_tasks_running: int
    active_api_keys: int
    active_proxies: int
    site_rules_count: int
    system_parameters_count: int
    timestamp: datetime
