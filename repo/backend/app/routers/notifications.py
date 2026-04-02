"""
Notifications & Delivery Management
=====================================
In-app notifications with offline retry logic and per-user preferences.

Delivery model
--------------
Notifications are written to the DB immediately.  The GET /notifications
endpoint triggers `process_due_retries()` at the start of each request
so any 'retrying' items that are now due are promoted to 'delivered'
before returning results.

Order-status events (accepted / arrived / completed / exception) are
emitted via POST /notifications/order-status.  The system checks the
recipient's preferences before creating the row.

RBAC
----
  Create (general): admin
  Emit order-status: admin, clinic_staff, catalog_manager
  Read own:         all authenticated
  Preferences:      self only
  Metrics:          admin only
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.core.notification_delivery import (
    create_and_deliver,
    get_delivery_metrics,
    process_due_retries,
    user_wants_notification,
)
from app.database import get_db
from app.models.notification import Notification, NotificationStatus, NotificationType
from app.models.thread import UserNotificationPreference
from app.models.user import User
from app.schemas.notification import (
    DeliveryMetricsResponse,
    MarkReadRequest,
    NotificationBrief,
    NotificationCreate,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    NotificationResponse,
    ORDER_STATUS_SUBTYPES as _SCHEMA_SUBTYPES,
    OrderStatusNotificationCreate,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])

_ORDER_STATUS_TITLES = {
    "accepted":  "Order Accepted",
    "arrived":   "Order Arrived",
    "completed": "Order Completed",
    "exception": "Order Exception",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_404(db: Session, notif_id: int, current_user: User) -> Notification:
    n = db.execute(
        select(Notification).where(Notification.id == notif_id)
    ).scalar_one_or_none()
    if not n:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if n.recipient_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return n


def _get_or_create_prefs(db: Session, user_id: int) -> UserNotificationPreference:
    prefs = db.execute(
        select(UserNotificationPreference).where(UserNotificationPreference.user_id == user_id)
    ).scalar_one_or_none()
    if not prefs:
        prefs = UserNotificationPreference(user_id=user_id)
        db.add(prefs)
        db.flush()
    return prefs


# ---------------------------------------------------------------------------
# Notification CRUD
# ---------------------------------------------------------------------------

@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
def create_notification(
    payload: NotificationCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """
    Create and immediately attempt delivery of an arbitrary notification.
    Preference check is skipped for admin-created notifications.
    """
    n = create_and_deliver(
        db,
        recipient_id=payload.recipient_id,
        notification_type=payload.notification_type,
        title=payload.title,
        body=payload.body,
        event_subtype=payload.event_subtype,
        related_entity_type=payload.related_entity_type,
        related_entity_id=payload.related_entity_id,
    )
    db.commit()
    db.refresh(n)
    return n


@router.post(
    "/order-status",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
)
def emit_order_status_notification(
    payload: OrderStatusNotificationCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin", "clinic_staff", "catalog_manager")),
):
    """
    Emit an order-status notification (accepted / arrived / completed / exception).

    - Validates that event_subtype is a known order-status value.
    - Respects the recipient's notification preferences.
    - Creates and immediately attempts delivery.
    """
    if payload.event_subtype not in _SCHEMA_SUBTYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"event_subtype must be one of: {sorted(_SCHEMA_SUBTYPES)}",
        )

    # Preference check
    if not user_wants_notification(
        payload.recipient_id,
        NotificationType.info,
        payload.event_subtype,
        db,
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Recipient has disabled '{payload.event_subtype}' notifications. "
                "Notification not created."
            ),
        )

    title = _ORDER_STATUS_TITLES.get(payload.event_subtype, "Order Update")
    body = f"Your order #{payload.order_id} status: {payload.event_subtype.upper()}."
    if payload.extra_body:
        body = f"{body} {payload.extra_body}"

    n = create_and_deliver(
        db,
        recipient_id=payload.recipient_id,
        notification_type=NotificationType.info,
        title=title,
        body=body,
        event_subtype=payload.event_subtype,
        related_entity_type="order",
        related_entity_id=payload.order_id,
    )
    db.commit()
    db.refresh(n)
    return n


@router.get("", response_model=list[NotificationBrief])
def list_notifications(
    unread_only: bool = Query(default=False),
    notification_type: NotificationType | None = Query(default=None),
    event_subtype: str | None = Query(default=None, max_length=50),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch notifications for the authenticated user.
    Triggers the retry engine before returning results — any due retries
    are processed and committed so clients always see up-to-date statuses.
    """
    processed = process_due_retries(db)
    if processed:
        db.commit()

    q = select(Notification).where(Notification.recipient_id == current_user.id)
    if unread_only:
        q = q.where(Notification.is_read == False)  # noqa: E712
    if notification_type is not None:
        q = q.where(Notification.notification_type == notification_type)
    if event_subtype is not None:
        q = q.where(Notification.event_subtype == event_subtype)

    q = q.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
    return db.execute(q).scalars().all()


@router.get("/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns the count of unread notifications — use for badge rendering."""
    from sqlalchemy import func
    count = db.execute(
        select(func.count(Notification.id)).where(
            Notification.recipient_id == current_user.id,
            Notification.is_read == False,  # noqa: E712
        )
    ).scalar_one()
    return {"unread_count": count}


@router.get("/{notif_id}", response_model=NotificationResponse)
def get_notification(
    notif_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_or_404(db, notif_id, current_user)


@router.patch("/{notif_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notif_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a single notification as read."""
    n = _get_or_404(db, notif_id, current_user)
    if not n.is_read:
        n.is_read = True
        n.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(n)
    return n


@router.post("/mark-read", status_code=status.HTTP_204_NO_CONTENT)
def bulk_mark_read(
    payload: MarkReadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a batch of notifications as read (only own notifications)."""
    now = datetime.now(timezone.utc)
    rows = db.execute(
        select(Notification).where(
            Notification.id.in_(payload.notification_ids),
            Notification.recipient_id == current_user.id,
            Notification.is_read == False,  # noqa: E712
        )
    ).scalars().all()
    for n in rows:
        n.is_read = True
        n.read_at = now
    db.commit()


@router.post("/mark-all-read", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark every unread notification for the current user as read."""
    now = datetime.now(timezone.utc)
    rows = db.execute(
        select(Notification).where(
            Notification.recipient_id == current_user.id,
            Notification.is_read == False,  # noqa: E712
        )
    ).scalars().all()
    for n in rows:
        n.is_read = True
        n.read_at = now
    db.commit()


@router.delete("/{notif_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notif_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete (dismiss) a notification permanently."""
    n = _get_or_404(db, notif_id, current_user)
    db.delete(n)
    db.commit()


# ---------------------------------------------------------------------------
# Delivery metrics (admin only)
# ---------------------------------------------------------------------------

@router.get("/admin/metrics", response_model=DeliveryMetricsResponse)
def delivery_metrics(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """
    Aggregate delivery metrics computed from the notifications table.
    Offline-safe — no external monitoring required.
    """
    return get_delivery_metrics(db)


# ---------------------------------------------------------------------------
# Notification preferences (self)
# ---------------------------------------------------------------------------

@router.get("/preferences/me", response_model=NotificationPreferenceResponse)
def get_my_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve the current user's notification subscription preferences."""
    prefs = _get_or_create_prefs(db, current_user.id)
    db.commit()
    db.refresh(prefs)
    return prefs


@router.put("/preferences/me", response_model=NotificationPreferenceResponse)
def update_my_preferences(
    payload: NotificationPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update notification subscription preferences.
    Only provided fields are changed; omitted fields retain their current values.
    """
    prefs = _get_or_create_prefs(db, current_user.id)
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=422, detail="No fields provided")
    for field, value in update_data.items():
        setattr(prefs, field, value)
    prefs.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(prefs)
    return prefs
