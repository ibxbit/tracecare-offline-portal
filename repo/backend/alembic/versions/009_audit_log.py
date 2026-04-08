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
    # Create enum type via raw SQL (IF NOT EXISTS for idempotency)
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

    # Create table via raw SQL to bypass SQLAlchemy's automatic enum type creation
    op.execute("""
        CREATE TABLE audit_logs (
            id            SERIAL PRIMARY KEY,
            event_type    auditeventtype NOT NULL,
            user_id       INTEGER REFERENCES users(id) ON DELETE SET NULL,
            username      VARCHAR(100),
            ip_address    VARCHAR(45),
            resource_type VARCHAR(100),
            resource_id   VARCHAR(100),
            detail        TEXT,
            http_method   VARCHAR(10),
            http_path     VARCHAR(500),
            created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX ix_audit_logs_id         ON audit_logs (id)")
    op.execute("CREATE INDEX ix_audit_logs_event_type ON audit_logs (event_type)")
    op.execute("CREATE INDEX ix_audit_logs_user_id    ON audit_logs (user_id)")
    op.execute("CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at)")
    op.execute("CREATE INDEX ix_audit_logs_event_user    ON audit_logs (event_type, user_id)")
    op.execute("CREATE INDEX ix_audit_logs_created_event ON audit_logs (created_at, event_type)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_created_event")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_event_user")
    op.drop_table("audit_logs")
    op.execute("DROP TYPE IF EXISTS auditeventtype")
