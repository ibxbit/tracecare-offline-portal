"""Add Admin Console tables: site_rules, system_parameters, admin_tasks, proxy_pool_entries, api_keys.

Revision ID: 008_admin_console
Revises: 007_cms_page_type
Create Date: 2024-01-08 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008_admin_console"
down_revision: Union[str, None] = "007_cms_page_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Shared ENUM type names
_VALUE_TYPE = sa.Enum(
    "string", "integer", "boolean", "decimal", "json",
    name="valuetype",
)
_TASK_STATUS = sa.Enum(
    "pending", "running", "completed", "failed", "cancelled",
    name="taskstatus",
)
_PROXY_PROTO = sa.Enum(
    "http", "https", "socks5",
    name="proxyprotocol",
)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Shared ENUM types (idempotent creation)
    # ------------------------------------------------------------------
    # Drop valuetype ENUM if it already exists (for idempotency in dev/test)
    op.execute("""
    DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'valuetype') THEN
            DROP TYPE valuetype;
        END IF;
    END $$;
    """)
    _VALUE_TYPE.create(op.get_bind(), checkfirst=True)
    _TASK_STATUS.create(op.get_bind(), checkfirst=True)
    _PROXY_PROTO.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # 2. site_rules
    # ------------------------------------------------------------------
    op.create_table(
        "site_rules",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True, index=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("value_type", sa.Enum(
            "string", "integer", "boolean", "decimal", "json",
            name="valuetype", create_type=False,
        ), nullable=False, server_default="string"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )

    # ------------------------------------------------------------------
    # 3. system_parameters
    # ------------------------------------------------------------------
    op.create_table(
        "system_parameters",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("key", sa.String(200), nullable=False, unique=True, index=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("value_type", sa.Enum(
            "string", "integer", "boolean", "decimal", "json",
            name="valuetype", create_type=False,
        ), nullable=False, server_default="string"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_readonly", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("updated_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )

    # Seed read-only system parameters that capture the deployment baseline
    op.execute(
        """
        INSERT INTO system_parameters (key, value, value_type, description, is_readonly)
        VALUES
          ('app.version',         '1.0.0',     'string',  'Application version',                      true),
          ('app.environment',     'production', 'string',  'Deployment environment',                   false),
          ('exam.max_items',      '200',        'integer', 'Max exam items per package',               false),
          ('review.rate_limit_minutes', '10',   'integer', 'Min minutes between reviews per user',     false),
          ('cms.max_revisions',   '30',         'integer', 'Max stored CMS revisions per page',        true),
          ('notification.retry_schedule', '[1,5,15]', 'json', 'Delivery retry schedule in minutes',   true)
        ON CONFLICT (key) DO NOTHING
        """
    )

    # ------------------------------------------------------------------
    # 4. admin_tasks
    # ------------------------------------------------------------------
    op.create_table(
        "admin_tasks",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("task_type", sa.String(100), nullable=False, index=True),
        sa.Column("status", sa.Enum(
            "pending", "running", "completed", "failed", "cancelled",
            name="taskstatus", create_type=False,
        ), nullable=False, server_default="pending", index=True),
        sa.Column("priority", sa.Integer, nullable=False, server_default="5"),
        sa.Column("payload_json", sa.Text, nullable=True),
        sa.Column("result_json",  sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_by",  sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("assigned_to", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("external_system", sa.String(100), nullable=True, index=True),
        sa.Column("external_ref",    sa.String(200), nullable=True),
        sa.Column("scheduled_at",  sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at",    sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at",  sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint("priority >= 1 AND priority <= 10", name="ck_admin_tasks_priority_range"),
    )
    op.create_index("ix_admin_tasks_status_priority", "admin_tasks", ["status", "priority"])

    # ------------------------------------------------------------------
    # 5. proxy_pool_entries
    # ------------------------------------------------------------------
    op.create_table(
        "proxy_pool_entries",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("host",  sa.String(255), nullable=False),
        sa.Column("port",  sa.Integer,     nullable=False),
        sa.Column("protocol", sa.Enum(
            "http", "https", "socks5",
            name="proxyprotocol", create_type=False,
        ), nullable=False, server_default="http"),
        sa.Column("username",           sa.String(200), nullable=True),
        sa.Column("password_encrypted", sa.Text,        nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("weight",    sa.Integer, nullable=False, server_default="5"),
        sa.Column("region",    sa.String(100), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_healthy",      sa.Boolean, nullable=True),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint("port >= 1 AND port <= 65535",   name="ck_proxy_pool_port_range"),
        sa.CheckConstraint("weight >= 1 AND weight <= 10",  name="ck_proxy_pool_weight_range"),
    )

    # ------------------------------------------------------------------
    # 6. api_keys
    # ------------------------------------------------------------------
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("label",       sa.String(200), nullable=False),
        sa.Column("system_name", sa.String(200), nullable=False, index=True),
        sa.Column("key_hash",    sa.String(64),  nullable=False, unique=True, index=True),
        sa.Column("key_prefix",  sa.String(12),  nullable=False),
        sa.Column("rate_limit_per_minute", sa.Integer, nullable=False, server_default="60"),
        sa.Column("allowed_ips", sa.Text, nullable=True),
        sa.Column("is_active",   sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by",  sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_count",  sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at",  sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("expires_at",  sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "rate_limit_per_minute >= 1 AND rate_limit_per_minute <= 6000",
            name="ck_api_keys_rate_limit_range",
        ),
    )


def downgrade() -> None:
    op.drop_table("api_keys")
    op.drop_table("proxy_pool_entries")
    op.drop_index("ix_admin_tasks_status_priority", table_name="admin_tasks")
    op.drop_table("admin_tasks")
    op.drop_table("system_parameters")
    op.drop_table("site_rules")
    _PROXY_PROTO.drop(op.get_bind(), checkfirst=True)
    _TASK_STATUS.drop(op.get_bind(), checkfirst=True)
    _VALUE_TYPE.drop(op.get_bind(), checkfirst=True)
