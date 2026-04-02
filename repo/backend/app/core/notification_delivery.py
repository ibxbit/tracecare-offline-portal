"""
Offline Notification Delivery Engine
======================================
In a fully offline/on-prem deployment there is no push gateway, SMTP server,
or SMS provider.  "Delivery" therefore means:
  1. The notification row is written to the database (already done at creation).
  2. The delivery engine confirms the row is visible and updates status to
     'delivered', recording the timestamp.
  3. The client polls GET /notifications to pick up new items (badge counts,
     read status, etc.).

Retry schedule (matches RETRY_SCHEDULE_MINUTES = [1, 5, 15])
-------------------------------------------------------------
  attempt 0  → immediate (at creation time)
  attempt 1  → next_retry_at = created_at + 1 min
  attempt 2  → next_retry_at = last_attempted_at + 5 min
  attempt 3  → next_retry_at = last_attempted_at + 15 min
  attempt 4+ → status = 'failed', failure_reason set

The 'failure' case in an offline DB context is:
  - The DB write itself succeeded but the notification could not be confirmed
    (e.g. a constraint violation, the recipient does not exist, etc.).
  - Callers may also force-fail a notification by calling `mark_failed()`.

Usage
-----
Call `process_due_retries(db)` periodically from a background task or
at the start of the GET /notifications endpoint to ensure any stale
'retrying' notifications are promoted to 'delivered'.

All functions receive an open SQLAlchemy Session and do NOT commit;
the caller is responsible for committing.

Metrics
-------
`get_delivery_metrics(db)` queries the notifications table directly and
returns aggregate counts — no separate metrics table needed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.notification import (
    MAX_DELIVERY_ATTEMPTS,
    RETRY_SCHEDULE_MINUTES,
    Notification,
    NotificationStatus,
    NotificationType,
)


# ---------------------------------------------------------------------------
# Core delivery logic
# ---------------------------------------------------------------------------

def attempt_delivery(notification: Notification, db: Session) -> bool:
    """
    Try to mark *notification* as delivered.

    In the offline model this always succeeds as long as the row exists
    and the recipient is a valid user.  Returns True on success.

    Does NOT commit — caller must commit.
    """
    now = datetime.now(timezone.utc)
    notification.delivery_attempts += 1
    notification.last_attempted_at = now

    # Verify recipient still exists and is active
    from app.models.user import User
    recipient = db.execute(
        select(User).where(User.id == notification.recipient_id, User.is_active == True)  # noqa: E712
    ).scalar_one_or_none()

    if recipient is None:
        _schedule_retry_or_fail(notification, reason="Recipient not found or inactive")
        return False

    notification.status = NotificationStatus.delivered
    notification.delivered_at = now
    notification.next_retry_at = None
    return True


def _schedule_retry_or_fail(notification: Notification, reason: str = "") -> None:
    """Increment attempt counter and schedule next retry or mark failed."""
    now = datetime.now(timezone.utc)
    attempt = notification.delivery_attempts   # already incremented by caller

    # Determine whether there are retry slots left
    # attempt 0 = initial; attempts 1,2,3 = scheduled retries; attempt 4 = final failure
    retry_index = attempt - 1  # which RETRY_SCHEDULE_MINUTES index to use
    if retry_index < len(RETRY_SCHEDULE_MINUTES):
        delay = RETRY_SCHEDULE_MINUTES[retry_index]
        notification.status = NotificationStatus.retrying
        notification.next_retry_at = now + timedelta(minutes=delay)
    else:
        notification.status = NotificationStatus.failed
        notification.next_retry_at = None
        notification.failure_reason = reason or "Maximum delivery attempts reached"


def process_due_retries(db: Session) -> int:
    """
    Find all 'retrying' notifications whose next_retry_at has passed
    and attempt re-delivery.  Returns the number of notifications processed.

    Call this at the top of the GET /notifications endpoint or from a
    lightweight background task.  Does NOT commit.
    """
    now = datetime.now(timezone.utc)
    due = db.execute(
        select(Notification).where(
            Notification.status == NotificationStatus.retrying,
            Notification.next_retry_at <= now,
        )
    ).scalars().all()

    for n in due:
        attempt_delivery(n, db)

    return len(due)


def create_and_deliver(
    db: Session,
    *,
    recipient_id: int,
    notification_type: NotificationType,
    title: str,
    body: str,
    event_subtype: str | None = None,
    related_entity_type: str | None = None,
    related_entity_id: int | None = None,
) -> Notification:
    """
    Create a notification row and immediately attempt delivery.
    On failure the row is left in 'retrying' status with next_retry_at set.
    Does NOT commit.
    """
    now = datetime.now(timezone.utc)
    n = Notification(
        recipient_id=recipient_id,
        notification_type=notification_type,
        event_subtype=event_subtype,
        title=title,
        body=body,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        status=NotificationStatus.pending,
        delivery_attempts=0,
        created_at=now,
    )
    db.add(n)
    db.flush()   # get n.id; does not commit
    attempt_delivery(n, db)
    return n


def mark_failed(notification: Notification, reason: str) -> None:
    """Force-mark a notification as failed (e.g. invalid recipient)."""
    notification.status = NotificationStatus.failed
    notification.next_retry_at = None
    notification.failure_reason = reason


# ---------------------------------------------------------------------------
# Preference check
# ---------------------------------------------------------------------------

_SUBTYPE_TO_PREF = {
    "accepted":  "notify_order_accepted",
    "arrived":   "notify_order_arrived",
    "completed": "notify_order_completed",
    "exception": "notify_order_exception",
}

_TYPE_TO_PREF = {
    NotificationType.system:  "notify_system",
    NotificationType.info:    "notify_info",
}


def user_wants_notification(
    recipient_id: int,
    notification_type: NotificationType,
    event_subtype: str | None,
    db: Session,
) -> bool:
    """
    Return False if the user has explicitly opted out of this category.
    Defaults to True when no preference row exists.
    """
    from app.models.thread import UserNotificationPreference
    prefs = db.execute(
        select(UserNotificationPreference).where(
            UserNotificationPreference.user_id == recipient_id
        )
    ).scalar_one_or_none()

    if prefs is None:
        return True  # default-on

    # Order-status subtype check
    if event_subtype and event_subtype in _SUBTYPE_TO_PREF:
        return bool(getattr(prefs, _SUBTYPE_TO_PREF[event_subtype], True))

    # Message types
    if notification_type == NotificationType.info:
        return prefs.notify_info
    if notification_type == NotificationType.system:
        return prefs.notify_system

    return True  # all other types default to enabled


# ---------------------------------------------------------------------------
# Delivery metrics (computed from the notifications table)
# ---------------------------------------------------------------------------

class DeliveryMetrics(TypedDict):
    total: int
    delivered: int
    retrying: int
    failed: int
    pending: int
    delivery_rate_pct: float
    avg_attempts_on_delivered: float
    by_type: dict[str, dict[str, int]]


def get_delivery_metrics(db: Session) -> DeliveryMetrics:
    """
    Compute delivery metrics directly from the notifications table.
    Grouped by status and notification_type.
    No separate metrics table required — offline-safe.
    """
    rows = db.execute(
        select(
            Notification.notification_type,
            Notification.status,
            func.count(Notification.id).label("cnt"),
        ).group_by(Notification.notification_type, Notification.status)
    ).all()

    totals: dict[str, int] = {
        "total": 0,
        "delivered": 0,
        "retrying": 0,
        "failed": 0,
        "pending": 0,
    }
    by_type: dict[str, dict[str, int]] = {}

    for row in rows:
        ntype = row.notification_type.value if hasattr(row.notification_type, "value") else str(row.notification_type)
        nstatus = row.status.value if hasattr(row.status, "value") else str(row.status)
        cnt = row.cnt

        totals["total"] += cnt
        totals[nstatus] = totals.get(nstatus, 0) + cnt

        if ntype not in by_type:
            by_type[ntype] = {"delivered": 0, "failed": 0, "retrying": 0, "pending": 0}
        by_type[ntype][nstatus] = by_type[ntype].get(nstatus, 0) + cnt

    # Average attempts on successfully delivered notifications
    avg_row = db.execute(
        select(func.avg(Notification.delivery_attempts)).where(
            Notification.status == NotificationStatus.delivered
        )
    ).scalar()
    avg_attempts = float(avg_row) if avg_row is not None else 0.0

    total = totals["total"]
    delivered = totals.get("delivered", 0)
    rate = round((delivered / total * 100), 2) if total else 0.0

    return DeliveryMetrics(
        total=total,
        delivered=delivered,
        retrying=totals.get("retrying", 0),
        failed=totals.get("failed", 0),
        pending=totals.get("pending", 0),
        delivery_rate_pct=rate,
        avg_attempts_on_delivered=round(avg_attempts, 2),
        by_type=by_type,
    )
