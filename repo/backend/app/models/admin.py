"""Admin Console models — site rules, system parameters, tasks, proxy pool, API keys."""
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text,
    Enum as SAEnum, CheckConstraint, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Shared enum
# ---------------------------------------------------------------------------

class ValueType(str, enum.Enum):
    string = "string"
    integer = "integer"
    boolean = "boolean"
    decimal = "decimal"
    json = "json"


# ---------------------------------------------------------------------------
# Site rules — named toggleable configuration values
# ---------------------------------------------------------------------------

class SiteRule(Base):
    """Configurable site-wide business rules (e.g. max_exam_items_per_package = 50)."""
    __tablename__ = "site_rules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[ValueType] = mapped_column(
        SAEnum(ValueType), nullable=False, default=ValueType.string
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])


# ---------------------------------------------------------------------------
# System parameters — read-only or editable key/value store
# ---------------------------------------------------------------------------

class SystemParameter(Base):
    """Low-level system configuration; some entries are read-only (set by migrations)."""
    __tablename__ = "system_parameters"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[ValueType] = mapped_column(
        SAEnum(ValueType), nullable=False, default=ValueType.string
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_readonly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    updater = relationship("User", foreign_keys=[updated_by])


# ---------------------------------------------------------------------------
# Admin tasks — work items triggerable by admin UI or external on-prem systems
# ---------------------------------------------------------------------------

class TaskStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class TaskPriority(int, enum.Enum):
    low = 1
    normal = 5
    high = 10


class AdminTask(Base):
    """
    Admin-managed work items.
    Can be triggered by internal admins or external on-prem systems via API key.
    External systems supply external_system + external_ref for correlation.
    """
    __tablename__ = "admin_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus), nullable=False, default=TaskStatus.pending, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    # Arbitrary JSON payload / result (stored as text to stay pure-SQL)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Authorship — one of these is always set
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    # External on-prem system correlation
    external_system: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    external_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)

    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    creator = relationship("User", foreign_keys=[created_by])
    assignee = relationship("User", foreign_keys=[assigned_to])

    __table_args__ = (
        CheckConstraint("priority >= 1 AND priority <= 10", name="ck_admin_tasks_priority_range"),
    )


# ---------------------------------------------------------------------------
# Proxy pool — internal network proxies (on-prem only)
# ---------------------------------------------------------------------------

class ProxyProtocol(str, enum.Enum):
    http = "http"
    https = "https"
    socks5 = "socks5"


class ProxyPoolEntry(Base):
    """
    Internal-network proxy entries.
    Passwords are Fernet-encrypted at the application layer.
    Health status is set by an explicit admin-triggered health-check action.
    """
    __tablename__ = "proxy_pool_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    protocol: Mapped[ProxyProtocol] = mapped_column(
        SAEnum(ProxyProtocol), nullable=False, default=ProxyProtocol.http
    )

    username: Mapped[str | None] = mapped_column(String(200), nullable=True)
    password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)

    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_healthy: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        CheckConstraint("port >= 1 AND port <= 65535", name="ck_proxy_pool_port_range"),
        CheckConstraint("weight >= 1 AND weight <= 10", name="ck_proxy_pool_weight_range"),
    )


# ---------------------------------------------------------------------------
# API keys — machine auth for external on-prem systems
# ---------------------------------------------------------------------------

class ApiKey(Base):
    """
    API keys issued to external on-prem systems.
    Only the SHA-256 hash of the raw key is stored; the raw key is shown once at creation.
    Rate limit is enforced in-memory (sliding window) per key_hash.
    """
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    system_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)    # first chars, display only

    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    allowed_ips: Mapped[str | None] = mapped_column(Text, nullable=True)   # comma-separated IPs/CIDRs

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        CheckConstraint(
            "rate_limit_per_minute >= 1 AND rate_limit_per_minute <= 6000",
            name="ck_api_keys_rate_limit_range",
        ),
    )
