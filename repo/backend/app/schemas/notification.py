from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field

from app.models.notification import NotificationStatus, NotificationType


# Order-status event subtypes
ORDER_STATUS_SUBTYPES = {"accepted", "arrived", "completed", "exception"}


class NotificationCreate(BaseModel):
    recipient_id: int
    notification_type: NotificationType = NotificationType.info
    event_subtype: str | None = Field(
        default=None,
        max_length=50,
        description="For order-status events: accepted | arrived | completed | exception",
    )
    title: Annotated[str, Field(min_length=1, max_length=255)]
    body: Annotated[str, Field(min_length=1)]
    related_entity_type: str | None = Field(default=None, max_length=50)
    related_entity_id: int | None = None


class OrderStatusNotificationCreate(BaseModel):
    """Shorthand for emitting an order-status notification."""
    order_id: int
    recipient_id: int
    event_subtype: Annotated[str, Field(description="accepted | arrived | completed | exception")]
    extra_body: str | None = Field(
        default=None,
        max_length=500,
        description="Optional additional detail appended to the default message body",
    )


class NotificationResponse(BaseModel):
    id: int
    recipient_id: int
    notification_type: NotificationType
    event_subtype: str | None
    title: str
    body: str
    related_entity_type: str | None
    related_entity_id: int | None
    is_read: bool
    read_at: datetime | None
    status: NotificationStatus
    delivery_attempts: int
    last_attempted_at: datetime | None
    next_retry_at: datetime | None
    delivered_at: datetime | None
    failure_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationBrief(BaseModel):
    """Lightweight listing item for badge / feed rendering."""
    id: int
    notification_type: NotificationType
    event_subtype: str | None
    title: str
    is_read: bool
    related_entity_type: str | None
    related_entity_id: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MarkReadRequest(BaseModel):
    notification_ids: list[int] = Field(min_length=1, max_length=200)


class DeliveryMetricsResponse(BaseModel):
    total: int
    delivered: int
    retrying: int
    failed: int
    pending: int
    delivery_rate_pct: float
    avg_attempts_on_delivered: float
    by_type: dict[str, dict[str, int]]


# ---------------------------------------------------------------------------
# Notification preferences
# ---------------------------------------------------------------------------

class NotificationPreferenceResponse(BaseModel):
    id: int
    user_id: int
    notify_order_accepted: bool
    notify_order_arrived: bool
    notify_order_completed: bool
    notify_order_exception: bool
    notify_new_message: bool
    notify_thread_reply: bool
    notify_system: bool
    notify_info: bool
    updated_at: datetime

    model_config = {"from_attributes": True}


class NotificationPreferenceUpdate(BaseModel):
    notify_order_accepted: bool | None = None
    notify_order_arrived: bool | None = None
    notify_order_completed: bool | None = None
    notify_order_exception: bool | None = None
    notify_new_message: bool | None = None
    notify_thread_reply: bool | None = None
    notify_system: bool | None = None
    notify_info: bool | None = None
