"""
Conversation threads and messaging preferences.

Thread model
------------
A Thread groups messages between users, optionally anchored to an order.

Virtual-contact relay
---------------------
Each ThreadParticipant row carries an optional virtual_contact_id — a
randomly-generated masked alias (e.g. "USR-A3F9").  When the thread is
created with use_virtual_ids=True, senders are identified by their alias
in response payloads instead of their real username/user_id.
This provides an offline equivalent of a masked-number relay.

Notification preferences
------------------------
UserNotificationPreference stores per-user opt-in/opt-out flags for every
category of in-app notification.  Defaults to all enabled.
"""
import enum
import secrets
from datetime import datetime, timezone
from sqlalchemy import (
    String, Text, DateTime, ForeignKey, Boolean, Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


# ---------------------------------------------------------------------------
# Thread
# ---------------------------------------------------------------------------

class Thread(Base):
    """
    A conversation thread, optionally linked to an order.
    Messages within the thread are stored in ThreadMessage.
    Participants are tracked in ThreadParticipant.
    """
    __tablename__ = "threads"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id"), nullable=True, index=True
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # When True all senders appear as their virtual_contact_id alias
    use_virtual_ids: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    creator = relationship("User", foreign_keys=[created_by])
    order = relationship("Order", foreign_keys=[order_id])
    participants = relationship(
        "ThreadParticipant",
        back_populates="thread",
        cascade="all, delete-orphan",
    )
    messages = relationship(
        "ThreadMessage",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="ThreadMessage.created_at",
    )


class ThreadParticipant(Base):
    """
    Membership row linking a User to a Thread.

    virtual_contact_id — generated at join time when the thread uses
    virtual IDs.  Unique within the thread so participants can reply to
    specific aliases without knowing real identities.
    """
    __tablename__ = "thread_participants"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    thread_id: Mapped[int] = mapped_column(
        ForeignKey("threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Masked alias for virtual-relay threads (e.g. "USR-A3F9")
    virtual_contact_id: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Per-participant unread counter (incremented by message delivery, reset on read)
    unread_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    thread = relationship("Thread", back_populates="participants")
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("thread_id", "user_id", name="uq_thread_participants_thread_user"),
    )

    @staticmethod
    def generate_virtual_id() -> str:
        """Return a short masked alias, e.g. 'USR-A3F9'."""
        token = secrets.token_hex(2).upper()  # 4 hex chars
        return f"USR-{token}"


class ThreadMessage(Base):
    """
    A single message within a Thread.
    Body is Fernet-encrypted at rest (same key as direct messages).
    System messages (is_system_message=True) are injected automatically
    for order-status transitions and are not encrypted.
    """
    __tablename__ = "thread_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    thread_id: Mapped[int] = mapped_column(
        ForeignKey("threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    body_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    is_system_message: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    thread = relationship("Thread", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])


# ---------------------------------------------------------------------------
# User notification preferences
# ---------------------------------------------------------------------------

class UserNotificationPreference(Base):
    """
    Per-user opt-in/opt-out for each notification category.
    A missing row means all categories are enabled (default-on).
    """
    __tablename__ = "user_notification_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    # Order-status events
    notify_order_accepted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_order_arrived: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_order_completed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_order_exception: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Messaging
    notify_new_message: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_thread_reply: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # System / administrative
    notify_system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_info: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", foreign_keys=[user_id])
