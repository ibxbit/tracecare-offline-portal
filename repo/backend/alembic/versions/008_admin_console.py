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

# Shared ENUM type names — create_type=False prevents SQLAlchemy from
# auto-emitting CREATE TYPE when these objects are referenced in op.create_table;
# we manage type creation explicitly via raw SQL below.
_VALUE_TYPE = sa.Enum(
    "string", "integer", "boolean", "decimal", "json",
    name="valuetype",
    create_type=False,
)
_TASK_STATUS = sa.Enum(
    "pending", "running", "completed", "failed", "cancelled",
    name="taskstatus",
    create_type=False,
)
_PROXY_PROTO = sa.Enum(
    "http", "https", "socks5",
    name="proxyprotocol",
    create_type=False,
)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Shared ENUM types (idempotent via raw SQL)
    # ------------------------------------------------------------------
    op.execute("""
    DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'valuetype') THEN
            CREATE TYPE valuetype AS ENUM ('string', 'integer', 'boolean', 'decimal', 'json');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'taskstatus') THEN
            CREATE TYPE taskstatus AS ENUM ('pending', 'running', 'completed', 'failed', 'cancelled');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'proxyprotocol') THEN
            CREATE TYPE proxyprotocol AS ENUM ('http', 'https', 'socks5');
        END IF;
    END $$;
    """)

    # ------------------------------------------------------------------
    # 2-6. Tables — all created via raw SQL to avoid SQLAlchemy
    #       automatically re-issuing CREATE TYPE for named enum columns.
    # ------------------------------------------------------------------

    # site_rules
    op.execute("""
        CREATE TABLE site_rules (
            id          SERIAL PRIMARY KEY,
            name        VARCHAR(200) NOT NULL UNIQUE,
            value       TEXT NOT NULL,
            value_type  valuetype NOT NULL DEFAULT 'string',
            description TEXT,
            is_active   BOOLEAN NOT NULL DEFAULT TRUE,
            created_by  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            updated_by  INTEGER REFERENCES users(id) ON DELETE CASCADE,
            created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX ix_site_rules_id   ON site_rules (id)")
    op.execute("CREATE INDEX ix_site_rules_name ON site_rules (name)")

    # system_parameters
    op.execute("""
        CREATE TABLE system_parameters (
            id          SERIAL PRIMARY KEY,
            key         VARCHAR(200) NOT NULL UNIQUE,
            value       TEXT NOT NULL,
            value_type  valuetype NOT NULL DEFAULT 'string',
            description TEXT,
            is_readonly BOOLEAN NOT NULL DEFAULT FALSE,
            updated_by  INTEGER REFERENCES users(id) ON DELETE CASCADE,
            created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX ix_system_parameters_id  ON system_parameters (id)")
    op.execute("CREATE INDEX ix_system_parameters_key ON system_parameters (key)")

    op.execute("""
        INSERT INTO system_parameters (key, value, value_type, description, is_readonly)
        VALUES
          ('app.version',               '1.0.0',     'string',  'Application version',                    TRUE),
          ('app.environment',           'production', 'string',  'Deployment environment',                 FALSE),
          ('exam.max_items',            '200',        'integer', 'Max exam items per package',             FALSE),
          ('review.rate_limit_minutes', '10',         'integer', 'Min minutes between reviews per user',   FALSE),
          ('cms.max_revisions',         '30',         'integer', 'Max stored CMS revisions per page',      TRUE),
          ('notification.retry_schedule', '[1,5,15]', 'json',   'Delivery retry schedule in minutes',     TRUE)
        ON CONFLICT (key) DO NOTHING
    """)

    # admin_tasks
    op.execute("""
        CREATE TABLE admin_tasks (
            id              SERIAL PRIMARY KEY,
            name            VARCHAR(300) NOT NULL,
            task_type       VARCHAR(100) NOT NULL,
            status          taskstatus NOT NULL DEFAULT 'pending',
            priority        INTEGER NOT NULL DEFAULT 5,
            payload_json    TEXT,
            result_json     TEXT,
            error_message   TEXT,
            created_by      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            assigned_to     INTEGER REFERENCES users(id) ON DELETE CASCADE,
            external_system VARCHAR(100),
            external_ref    VARCHAR(200),
            scheduled_at    TIMESTAMP WITH TIME ZONE,
            started_at      TIMESTAMP WITH TIME ZONE,
            completed_at    TIMESTAMP WITH TIME ZONE,
            created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_admin_tasks_priority_range CHECK (priority >= 1 AND priority <= 10)
        )
    """)
    op.execute("CREATE INDEX ix_admin_tasks_id              ON admin_tasks (id)")
    op.execute("CREATE INDEX ix_admin_tasks_task_type       ON admin_tasks (task_type)")
    op.execute("CREATE INDEX ix_admin_tasks_status          ON admin_tasks (status)")
    op.execute("CREATE INDEX ix_admin_tasks_external_system ON admin_tasks (external_system)")
    op.execute("CREATE INDEX ix_admin_tasks_status_priority ON admin_tasks (status, priority)")

    # proxy_pool_entries
    op.execute("""
        CREATE TABLE proxy_pool_entries (
            id                 SERIAL PRIMARY KEY,
            label              VARCHAR(200) NOT NULL,
            host               VARCHAR(255) NOT NULL,
            port               INTEGER NOT NULL,
            protocol           proxyprotocol NOT NULL DEFAULT 'http',
            username           VARCHAR(200),
            password_encrypted TEXT,
            is_active          BOOLEAN NOT NULL DEFAULT TRUE,
            weight             INTEGER NOT NULL DEFAULT 5,
            region             VARCHAR(100),
            last_checked_at    TIMESTAMP WITH TIME ZONE,
            is_healthy         BOOLEAN,
            created_by         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_proxy_pool_port_range   CHECK (port   >= 1 AND port   <= 65535),
            CONSTRAINT ck_proxy_pool_weight_range CHECK (weight >= 1 AND weight <= 10)
        )
    """)
    op.execute("CREATE INDEX ix_proxy_pool_entries_id ON proxy_pool_entries (id)")

    # api_keys  (no enum columns — still raw SQL for consistency)
    op.execute("""
        CREATE TABLE api_keys (
            id                    SERIAL PRIMARY KEY,
            label                 VARCHAR(200) NOT NULL,
            system_name           VARCHAR(200) NOT NULL,
            key_hash              VARCHAR(64)  NOT NULL UNIQUE,
            key_prefix            VARCHAR(12)  NOT NULL,
            rate_limit_per_minute INTEGER NOT NULL DEFAULT 60,
            allowed_ips           TEXT,
            is_active             BOOLEAN NOT NULL DEFAULT TRUE,
            created_by            INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            last_used_at          TIMESTAMP WITH TIME ZONE,
            usage_count           INTEGER NOT NULL DEFAULT 0,
            created_at            TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            expires_at            TIMESTAMP WITH TIME ZONE,
            CONSTRAINT ck_api_keys_rate_limit_range
                CHECK (rate_limit_per_minute >= 1 AND rate_limit_per_minute <= 6000)
        )
    """)
    op.execute("CREATE INDEX ix_api_keys_id          ON api_keys (id)")
    op.execute("CREATE INDEX ix_api_keys_system_name ON api_keys (system_name)")
    op.execute("CREATE INDEX ix_api_keys_key_hash    ON api_keys (key_hash)")


def downgrade() -> None:
    op.drop_table("api_keys")
    op.drop_table("proxy_pool_entries")
    op.execute("DROP INDEX IF EXISTS ix_admin_tasks_status_priority")
    op.drop_table("admin_tasks")
    op.drop_table("system_parameters")
    op.drop_table("site_rules")
    op.execute("DROP TYPE IF EXISTS proxyprotocol")
    op.execute("DROP TYPE IF EXISTS taskstatus")
    op.execute("DROP TYPE IF EXISTS valuetype")
