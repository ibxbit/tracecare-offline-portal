"""Add conversation threads, notification preferences, and notification event_subtype.

Revision ID: 005_threads_notifications
Revises: 004_review_moderation
Create Date: 2024-01-05 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "005_threads_notifications"
down_revision: Union[str, None] = "004_review_moderation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Add event_subtype and read-state index to notifications
    # ------------------------------------------------------------------
    op.add_column(
        "notifications",
        sa.Column("event_subtype", sa.String(50), nullable=True),
    )
    op.create_index("ix_notifications_event_subtype", "notifications", ["event_subtype"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])
    op.create_index("ix_notifications_status", "notifications", ["status"])

    # ------------------------------------------------------------------
    # 2. Conversation threads
    # ------------------------------------------------------------------
    op.create_table(
        "threads",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id"), nullable=True, index=True),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("use_virtual_ids", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_archived", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )

    op.create_table(
        "thread_participants",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("thread_id", sa.Integer,
                  sa.ForeignKey("threads.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"),
                  nullable=False, index=True),
        sa.Column("virtual_contact_id", sa.String(20), nullable=True),
        sa.Column("unread_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("thread_id", "user_id", name="uq_thread_participants_thread_user"),
    )

    op.create_table(
        "thread_messages",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("thread_id", sa.Integer,
                  sa.ForeignKey("threads.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("sender_id", sa.Integer, sa.ForeignKey("users.id"),
                  nullable=False, index=True),
        sa.Column("body_encrypted", sa.Text, nullable=False),
        sa.Column("is_system_message", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )

    # ------------------------------------------------------------------
    # 3. User notification preferences
    # ------------------------------------------------------------------
    op.create_table(
        "user_notification_preferences",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"),
                  nullable=False, unique=True, index=True),
        sa.Column("notify_order_accepted", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notify_order_arrived",  sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notify_order_completed",sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notify_order_exception",sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notify_new_message",    sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notify_thread_reply",   sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notify_system",         sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notify_info",           sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("user_notification_preferences")
    op.drop_table("thread_messages")
    op.drop_table("thread_participants")
    op.drop_table("threads")
    op.drop_index("ix_notifications_status", table_name="notifications")
    op.drop_index("ix_notifications_is_read", table_name="notifications")
    op.drop_index("ix_notifications_event_subtype", table_name="notifications")
    op.drop_column("notifications", "event_subtype")
