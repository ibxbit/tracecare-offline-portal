"""
Messages & Conversation Threads
=================================
Two communication channels:

1. Direct messages — point-to-point, Fernet-encrypted body.
2. Conversation threads — multi-participant, order-anchored, encrypted,
   with optional virtual-contact relay (masked aliases).

Virtual-contact relay
---------------------
When a thread is created with use_virtual_ids=True, each participant is
assigned a random alias (e.g. "USR-A3F9").  API responses replace
sender_id with the sender's alias so participants cannot identify each
other's real accounts.  Moderators (admin) can always resolve aliases.

Thread notifications
--------------------
Sending a thread message fires in-app notifications for all other
participants (subject to their preferences).

RBAC
----
  Direct messages: all authenticated
  Threads: all authenticated (participants gate themselves)
  Virtual-contact resolve: admin only
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.dependencies import get_current_user, require_role
from app.core.encryption import encryptor
from app.core.notification_delivery import create_and_deliver, user_wants_notification
from app.database import get_db
from app.models.message import Message
from app.models.notification import NotificationType
from app.models.thread import Thread, ThreadMessage, ThreadParticipant, UserNotificationPreference
from app.models.user import User, UserRole
from app.schemas.message import (
    MessageCreate,
    MessageListResponse,
    MessageResponse,
    ThreadBrief,
    ThreadCreate,
    ThreadMessageCreate,
    ThreadMessageResponse,
    ThreadParticipantResponse,
    ThreadResponse,
    VirtualContactResponse,
)

router = APIRouter(prefix="/messages", tags=["messages"])


# ---------------------------------------------------------------------------
# Internal helpers — direct messages
# ---------------------------------------------------------------------------

def _get_msg_or_404(db: Session, msg_id: int, current_user: User) -> Message:
    msg = db.execute(select(Message).where(Message.id == msg_id)).scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if msg.sender_id != current_user.id and msg.recipient_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return msg


def _decrypt_body(encrypted: str) -> str:
    try:
        return encryptor.decrypt(encrypted)
    except Exception:
        return "[decryption error]"


# ---------------------------------------------------------------------------
# Internal helpers — threads
# ---------------------------------------------------------------------------

def _get_thread_or_404(db: Session, thread_id: int) -> Thread:
    thread = db.execute(
        select(Thread)
        .where(Thread.id == thread_id)
        .options(
            selectinload(Thread.participants),
            selectinload(Thread.messages),
        )
    ).scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    return thread


def _assert_participant(thread: Thread, user_id: int) -> ThreadParticipant:
    for p in thread.participants:
        if p.user_id == user_id:
            return p
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You are not a participant in this thread",
    )


def _sender_alias(thread: Thread, sender_id: int) -> str | None:
    """Return the sender's virtual alias if the thread uses masked IDs."""
    if not thread.use_virtual_ids:
        return None
    for p in thread.participants:
        if p.user_id == sender_id:
            return p.virtual_contact_id
    return None


def _build_thread_message_response(
    thread: Thread, tm: ThreadMessage
) -> ThreadMessageResponse:
    return ThreadMessageResponse(
        id=tm.id,
        thread_id=tm.thread_id,
        sender_id=tm.sender_id,
        sender_alias=_sender_alias(thread, tm.sender_id),
        body=None if tm.is_system_message else _decrypt_body(tm.body_encrypted),
        is_system_message=tm.is_system_message,
        created_at=tm.created_at,
    )


def _build_thread_response(thread: Thread, current_user_id: int) -> ThreadResponse:
    my_unread = 0
    for p in thread.participants:
        if p.user_id == current_user_id:
            my_unread = p.unread_count
            break

    messages = [_build_thread_message_response(thread, tm) for tm in thread.messages]
    participants = [ThreadParticipantResponse.model_validate(p) for p in thread.participants]

    return ThreadResponse(
        id=thread.id,
        subject=thread.subject,
        order_id=thread.order_id,
        created_by=thread.created_by,
        use_virtual_ids=thread.use_virtual_ids,
        is_archived=thread.is_archived,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        participants=participants,
        messages=messages,
        my_unread_count=my_unread,
    )


def _notify_thread_participants(
    thread: Thread,
    sender_id: int,
    db: Session,
) -> None:
    """Fire in-app notifications for all thread participants except the sender."""
    for p in thread.participants:
        if p.user_id == sender_id:
            continue
        if not user_wants_notification(p.user_id, NotificationType.info, None, db):
            continue
        create_and_deliver(
            db,
            recipient_id=p.user_id,
            notification_type=NotificationType.info,
            title=f"New message in: {thread.subject[:60]}",
            body=f"You have a new message in conversation '{thread.subject}'.",
            related_entity_type="thread",
            related_entity_id=thread.id,
        )


# ---------------------------------------------------------------------------
# Direct message endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def send_message(
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a direct encrypted message to another user."""
    recipient = db.execute(
        select(User).where(User.id == payload.recipient_id, User.is_active == True)  # noqa: E712
    ).scalar_one_or_none()
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found or inactive")

    encrypted = encryptor.encrypt(payload.body)
    msg = Message(
        sender_id=current_user.id,
        recipient_id=payload.recipient_id,
        subject=payload.subject,
        body_encrypted=encrypted,
    )
    db.add(msg)

    # Notify recipient if they want message notifications
    if user_wants_notification(payload.recipient_id, NotificationType.info, None, db):
        create_and_deliver(
            db,
            recipient_id=payload.recipient_id,
            notification_type=NotificationType.info,
            title=f"New message: {payload.subject[:60]}",
            body=f"You have a new message from {current_user.username}.",
            related_entity_type="message",
            related_entity_id=None,
        )

    db.commit()
    db.refresh(msg)
    return MessageResponse(
        id=msg.id,
        sender_id=msg.sender_id,
        recipient_id=msg.recipient_id,
        subject=msg.subject,
        body=payload.body,
        is_read=msg.is_read,
        created_at=msg.created_at,
    )


@router.get("/inbox", response_model=list[MessageListResponse])
def get_inbox(
    unread_only: bool = Query(default=False),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = (
        select(Message)
        .where(Message.recipient_id == current_user.id)
        .order_by(Message.created_at.desc())
    )
    if unread_only:
        q = q.where(Message.is_read == False)  # noqa: E712
    return db.execute(q.offset(skip).limit(limit)).scalars().all()


@router.get("/sent", response_model=list[MessageListResponse])
def get_sent(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    msgs = db.execute(
        select(Message)
        .where(Message.sender_id == current_user.id)
        .order_by(Message.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).scalars().all()
    return msgs


@router.get("/inbox/unread-count")
def inbox_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = db.execute(
        select(func.count(Message.id)).where(
            Message.recipient_id == current_user.id,
            Message.is_read == False,  # noqa: E712
        )
    ).scalar_one()
    return {"unread_count": count}


@router.get("/{message_id}", response_model=MessageResponse)
def get_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    msg = _get_msg_or_404(db, message_id, current_user)

    if msg.recipient_id == current_user.id and not msg.is_read:
        msg.is_read = True
        db.commit()
        db.refresh(msg)

    return MessageResponse(
        id=msg.id,
        sender_id=msg.sender_id,
        recipient_id=msg.recipient_id,
        subject=msg.subject,
        body=_decrypt_body(msg.body_encrypted),
        is_read=msg.is_read,
        created_at=msg.created_at,
    )


@router.patch("/{message_id}/read", response_model=MessageResponse)
def mark_message_read(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Explicitly mark a message as read without decrypting the body."""
    msg = _get_msg_or_404(db, message_id, current_user)
    if msg.recipient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the recipient can mark as read")
    if not msg.is_read:
        msg.is_read = True
        db.commit()
        db.refresh(msg)
    return MessageResponse(
        id=msg.id, sender_id=msg.sender_id, recipient_id=msg.recipient_id,
        subject=msg.subject, body=None, is_read=msg.is_read, created_at=msg.created_at,
    )


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    msg = _get_msg_or_404(db, message_id, current_user)
    db.delete(msg)
    db.commit()


# ---------------------------------------------------------------------------
# Thread endpoints
# ---------------------------------------------------------------------------

@router.post("/threads", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
def create_thread(
    payload: ThreadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a conversation thread.

    - The creator is automatically added as a participant.
    - participant_ids must all map to active users.
    - When use_virtual_ids=True, every participant gets a random alias;
      senders appear in responses as that alias.
    - The initial_message is posted as the first ThreadMessage.
    """
    # Validate all participant IDs (include creator)
    all_ids = list({current_user.id} | set(payload.participant_ids))
    users_found = db.execute(
        select(User).where(User.id.in_(all_ids), User.is_active == True)  # noqa: E712
    ).scalars().all()
    found_ids = {u.id for u in users_found}
    missing = set(all_ids) - found_ids
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"User IDs not found or inactive: {sorted(missing)}",
        )

    # Validate order if provided
    if payload.order_id is not None:
        from app.models.order import Order
        order = db.execute(select(Order).where(Order.id == payload.order_id)).scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=422, detail=f"Order {payload.order_id} not found")

    now = datetime.now(timezone.utc)
    thread = Thread(
        subject=payload.subject.strip(),
        order_id=payload.order_id,
        created_by=current_user.id,
        use_virtual_ids=payload.use_virtual_ids,
    )
    db.add(thread)
    db.flush()

    # Add participants
    used_aliases: set[str] = set()
    for uid in all_ids:
        alias = None
        if payload.use_virtual_ids:
            # Ensure alias uniqueness within this thread
            while True:
                candidate = ThreadParticipant.generate_virtual_id()
                if candidate not in used_aliases:
                    alias = candidate
                    used_aliases.add(alias)
                    break
        participant = ThreadParticipant(
            thread_id=thread.id,
            user_id=uid,
            virtual_contact_id=alias,
            unread_count=0,
            joined_at=now,
        )
        db.add(participant)

    db.flush()

    # Post the initial message
    encrypted_body = encryptor.encrypt(payload.initial_message)
    first_msg = ThreadMessage(
        thread_id=thread.id,
        sender_id=current_user.id,
        body_encrypted=encrypted_body,
        is_system_message=False,
    )
    db.add(first_msg)

    # Increment unread for everyone except the creator
    for p in db.execute(
        select(ThreadParticipant).where(
            ThreadParticipant.thread_id == thread.id,
            ThreadParticipant.user_id != current_user.id,
        )
    ).scalars().all():
        p.unread_count += 1

    db.commit()

    # Reload full thread for response
    thread = _get_thread_or_404(db, thread.id)

    # Send notifications after commit
    _notify_thread_participants(thread, current_user.id, db)
    db.commit()

    return _build_thread_response(thread, current_user.id)


@router.get("/threads", response_model=list[ThreadBrief])
def list_threads(
    archived: bool = Query(default=False),
    order_id: int | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List threads where the current user is a participant."""
    # Get thread IDs where user participates
    participant_rows = db.execute(
        select(ThreadParticipant).where(ThreadParticipant.user_id == current_user.id)
    ).scalars().all()
    thread_ids = [p.thread_id for p in participant_rows]
    unread_map = {p.thread_id: p.unread_count for p in participant_rows}

    if not thread_ids:
        return []

    q = (
        select(Thread)
        .where(Thread.id.in_(thread_ids), Thread.is_archived == archived)
        .options(selectinload(Thread.participants), selectinload(Thread.messages))
    )
    if order_id is not None:
        q = q.where(Thread.order_id == order_id)
    q = q.order_by(Thread.updated_at.desc()).offset(skip).limit(limit)

    threads = db.execute(q).scalars().all()

    briefs = []
    for t in threads:
        last_msg = t.messages[-1].created_at if t.messages else None
        briefs.append(ThreadBrief(
            id=t.id,
            subject=t.subject,
            order_id=t.order_id,
            use_virtual_ids=t.use_virtual_ids,
            is_archived=t.is_archived,
            participant_count=len(t.participants),
            last_message_at=last_msg,
            my_unread_count=unread_map.get(t.id, 0),
            created_at=t.created_at,
        ))
    return briefs


@router.get("/threads/{thread_id}", response_model=ThreadResponse)
def get_thread(
    thread_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a thread with all messages (marks thread as read for current user)."""
    thread = _get_thread_or_404(db, thread_id)
    participant = _assert_participant(thread, current_user.id)

    # Mark as read: reset unread_count and set last_read_at
    participant.unread_count = 0
    participant.last_read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(thread)

    thread = _get_thread_or_404(db, thread_id)
    return _build_thread_response(thread, current_user.id)


@router.post(
    "/threads/{thread_id}/messages",
    response_model=ThreadMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def send_thread_message(
    thread_id: int,
    payload: ThreadMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Post a message to a thread. Only participants may post."""
    thread = _get_thread_or_404(db, thread_id)
    _assert_participant(thread, current_user.id)

    if thread.is_archived:
        raise HTTPException(status_code=409, detail="Cannot post to an archived thread")

    encrypted = encryptor.encrypt(payload.body)
    tm = ThreadMessage(
        thread_id=thread_id,
        sender_id=current_user.id,
        body_encrypted=encrypted,
        is_system_message=False,
    )
    db.add(tm)

    # Increment unread for other participants
    for p in thread.participants:
        if p.user_id != current_user.id:
            p.unread_count += 1

    # Touch thread.updated_at for ordering
    thread.updated_at = datetime.now(timezone.utc)

    db.flush()
    db.commit()
    db.refresh(tm)

    # Reload thread for alias resolution then notify
    thread = _get_thread_or_404(db, thread_id)
    _notify_thread_participants(thread, current_user.id, db)
    db.commit()

    return ThreadMessageResponse(
        id=tm.id,
        thread_id=tm.thread_id,
        sender_id=tm.sender_id,
        sender_alias=_sender_alias(thread, current_user.id),
        body=payload.body,
        is_system_message=False,
        created_at=tm.created_at,
    )


@router.patch("/threads/{thread_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_thread_read(
    thread_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reset the unread counter for the current user in this thread."""
    thread = _get_thread_or_404(db, thread_id)
    participant = _assert_participant(thread, current_user.id)
    participant.unread_count = 0
    participant.last_read_at = datetime.now(timezone.utc)
    db.commit()


@router.patch("/threads/{thread_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
def archive_thread(
    thread_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Archive a thread (creator or admin only)."""
    thread = _get_thread_or_404(db, thread_id)
    if thread.created_by != current_user.id and current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Only the thread creator or admin can archive")
    thread.is_archived = True
    db.commit()


# ---------------------------------------------------------------------------
# Virtual-contact relay
# ---------------------------------------------------------------------------

@router.get("/threads/{thread_id}/my-alias", response_model=VirtualContactResponse)
def get_my_virtual_alias(
    thread_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the current user's virtual alias in a thread."""
    thread = _get_thread_or_404(db, thread_id)
    participant = _assert_participant(thread, current_user.id)
    return VirtualContactResponse(
        thread_id=thread_id,
        user_id=current_user.id,
        virtual_contact_id=participant.virtual_contact_id,
        message=(
            "Virtual ID active — your identity is masked in this thread."
            if participant.virtual_contact_id
            else "This thread does not use virtual IDs."
        ),
    )


@router.get(
    "/threads/{thread_id}/resolve-alias/{alias}",
    response_model=VirtualContactResponse,
)
def resolve_virtual_alias(
    thread_id: int,
    alias: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """
    Resolve a virtual alias to the real user (admin only).
    Allows moderators to identify participants when needed.
    """
    participant = db.execute(
        select(ThreadParticipant).where(
            ThreadParticipant.thread_id == thread_id,
            ThreadParticipant.virtual_contact_id == alias,
        )
    ).scalar_one_or_none()
    if not participant:
        raise HTTPException(
            status_code=404,
            detail=f"Alias '{alias}' not found in thread {thread_id}",
        )
    return VirtualContactResponse(
        thread_id=thread_id,
        user_id=participant.user_id,
        virtual_contact_id=alias,
        message=f"Alias '{alias}' belongs to user_id={participant.user_id}.",
    )
