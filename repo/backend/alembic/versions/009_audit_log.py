"""Add audit_logs table for security event trail.

Revision ID: 009_audit_log
Revises: 008_admin_console
Create Date: 2024-01-09 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009_audit_log"
down_revision: Union[str, None] = "008_admin_console"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_AUDIT_EVENT_TYPE = sa.Enum(
    "login_success", "login_failure", "login_locked", "logout",
    "token_refresh", "token_revoked", "password_change",
    "account_locked", "account_unlocked",
    "sensitive_read", "export_csv", "file_download",
    "record_created", "record_updated", "record_deleted",
    "file_integrity_ok", "file_integrity_fail", "snapshot_created",
    "api_key_issued", "api_key_revoked", "api_key_rotated",
    "rate_limit_exceeded", "ip_blocked",
    name="auditeventtype",
    create_type=False,
)


def upgrade() -> None:
    op.execute("""
    DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'auditeventtype') THEN
            CREATE TYPE auditeventtype AS ENUM (
                'login_success', 'login_failure', 'login_locked', 'logout',
                'token_refresh', 'token_revoked', 'password_change',
                'account_locked', 'account_unlocked',
                'sensitive_read', 'export_csv', 'file_download',
                'record_created', 'record_updated', 'record_deleted',
                'file_integrity_ok', 'file_integrity_fail', 'snapshot_created',
                'api_key_issued', 'api_key_revoked', 'api_key_rotated',
                'rate_limit_exceeded', 'ip_blocked'
            );
        END IF;
    END $$;
    """)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("event_type", sa.Enum(
            "login_success", "login_failure", "login_locked", "logout",
            "token_refresh", "token_revoked", "password_change",
            "account_locked", "account_unlocked",
            "sensitive_read", "export_csv", "file_download",
            "record_created", "record_updated", "record_deleted",
            "file_integrity_ok", "file_integrity_fail", "snapshot_created",
            "api_key_issued", "api_key_revoked", "api_key_rotated",
            "rate_limit_exceeded", "ip_blocked",
            name="auditeventtype", create_type=False,
        ), nullable=False, index=True),
        sa.Column("user_id", sa.Integer,
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("username", sa.String(100), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("http_method", sa.String(10), nullable=True),
        sa.Column("http_path", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now(), index=True),
    )

    # Composite index for common query patterns
    op.create_index(
        "ix_audit_logs_event_user",
        "audit_logs",
        ["event_type", "user_id"],
    )
    op.create_index(
        "ix_audit_logs_created_event",
        "audit_logs",
        ["created_at", "event_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_event", table_name="audit_logs")
    op.drop_index("ix_audit_logs_event_user", table_name="audit_logs")
    op.drop_table("audit_logs")
    _AUDIT_EVENT_TYPE.drop(op.get_bind(), checkfirst=True)
