"""AuditLog — immutable, append-only record of security-relevant events.

Fields are intentionally narrow strings so the table never stores
sensitive content (no passwords, no tokens, no encrypted blobs).
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AuditEventType(str, enum.Enum):
    # Authentication
    login_success        = "login_success"
    login_failure        = "login_failure"
    login_locked         = "login_locked"
    logout               = "logout"
    token_refresh        = "token_refresh"
    token_revoked        = "token_revoked"
    password_change      = "password_change"
    account_locked       = "account_locked"
    account_unlocked     = "account_unlocked"

    # Data access
    sensitive_read       = "sensitive_read"     # e.g. exam findings decrypted
    export_csv           = "export_csv"         # any CSV export
    file_download        = "file_download"      # attachment/review image download

    # Mutations
    record_created       = "record_created"
    record_updated       = "record_updated"
    record_deleted       = "record_deleted"

    # Integrity
    file_integrity_ok    = "file_integrity_ok"
    file_integrity_fail  = "file_integrity_fail"
    snapshot_created     = "snapshot_created"   # revision / package version

    # Security
    api_key_issued       = "api_key_issued"
    api_key_revoked      = "api_key_revoked"
    api_key_rotated      = "api_key_rotated"
    rate_limit_exceeded  = "rate_limit_exceeded"
    ip_blocked           = "ip_blocked"


class AuditLog(Base):
    """
    Immutable audit trail row.  Never updated — only inserted and (admin) read.

    `detail` is a short free-form string (not JSON, not sensitive data).
    Avoid storing PII, passwords, tokens, or encrypted blobs here.
    """
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    event_type: Mapped[AuditEventType] = mapped_column(
        SAEnum(AuditEventType), nullable=False, index=True
    )

    # Who — nullable because some events (IP block) have no authenticated user
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Where
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6 max

    # What
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # HTTP context (no body content stored — only method + path)
    http_method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    http_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    user = relationship("User", foreign_keys=[user_id])
