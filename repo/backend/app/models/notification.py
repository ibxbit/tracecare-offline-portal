import enum
from datetime import datetime, timezone
from sqlalchemy import (
    String, Text, DateTime, ForeignKey, Enum as SAEnum, Integer, Boolean,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

# Retry schedule in minutes: first attempt immediately, then 1, 5, 15 min
RETRY_SCHEDULE_MINUTES = [1, 5, 15]
MAX_DELIVERY_ATTEMPTS = len(RETRY_SCHEDULE_MINUTES) + 1  # initial + 3 retries = 4


class NotificationStatus(str, enum.Enum):
    pending = "pending"
    delivered = "delivered"
    retrying = "retrying"
    failed = "failed"


class NotificationType(str, enum.Enum):
    info = "info"
    warning = "warning"
    error = "error"
    success = "success"
    system = "system"


class Notification(Base):
    """
    In-app notification for a user.

    Delivery model (offline-only):
      - Attempt 0: immediate on creation
      - Attempt 1: retry after 1 min  (next_retry_at)
      - Attempt 2: retry after 5 min
      - Attempt 3: retry after 15 min
      - status → 'failed' if all 4 attempts exhausted

    Order-status events use notification_type='order_status' and set
    event_subtype to one of: accepted | arrived | completed | exception
    """
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    recipient_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    notification_type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType), nullable=False, default=NotificationType.info
    )
    # For order-status events: accepted | arrived | completed | exception
    event_subtype: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # Reference to the entity that triggered this notification
    related_entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Read / dismiss state
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Delivery tracking
    status: Mapped[NotificationStatus] = mapped_column(
        SAEnum(NotificationStatus), nullable=False,
        default=NotificationStatus.pending, index=True,
    )
    delivery_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    recipient = relationship("User", foreign_keys=[recipient_id])

    __table_args__ = (
        CheckConstraint(
            f"delivery_attempts <= {MAX_DELIVERY_ATTEMPTS}",
            name="ck_notifications_max_attempts",
        ),
        CheckConstraint("delivery_attempts >= 0", name="ck_notifications_attempts_non_negative"),
    )
