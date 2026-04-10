from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, computed_field


# ---------------------------------------------------------------------------
# Direct messages (encrypted, point-to-point)
# ---------------------------------------------------------------------------

class MessageCreate(BaseModel):
    recipient_id: int
    subject: Annotated[str, Field(min_length=1, max_length=500)]
    body: Annotated[str, Field(min_length=1)]


class MessageResponse(BaseModel):
    id: int
    sender_id: int
    recipient_id: int
    subject: str
    body: str | None = None     # None when body decryption is unavailable
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageListResponse(BaseModel):
    id: int
    sender_id: int
    recipient_id: int
    subject: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Conversation threads
# ---------------------------------------------------------------------------

class ThreadCreate(BaseModel):
    subject: Annotated[str, Field(min_length=1, max_length=500)]
    order_id: int | None = Field(
        default=None,
        description="Anchor this thread to an order (optional)",
    )
    participant_ids: Annotated[list[int], Field(min_length=1, max_length=50)]
    initial_message: Annotated[str, Field(min_length=1)]
    use_virtual_ids: bool = Field(
        default=False,
        description=(
            "When True, senders appear as masked aliases (e.g. USR-A3F9) "
            "instead of real usernames — virtual-contact relay mode."
        ),
    )


class ThreadMessageCreate(BaseModel):
    body: Annotated[str, Field(min_length=1)]


class ThreadMessageResponse(BaseModel):
    id: int
    thread_id: int
    sender_id: int
    # When the thread uses virtual IDs, sender_alias is the masked contact ID;
    # otherwise it is None and the caller uses sender_id.
    sender_alias: str | None = None
    body: str | None = None     # decrypted; None on decryption error
    is_system_message: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ThreadParticipantResponse(BaseModel):
    user_id: int
    virtual_contact_id: str | None
    unread_count: int
    last_read_at: datetime | None
    joined_at: datetime

    model_config = {"from_attributes": True}


class ThreadResponse(BaseModel):
    id: int
    subject: str
    order_id: int | None
    created_by: int
    use_virtual_ids: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    participants: list[ThreadParticipantResponse]
    messages: list[ThreadMessageResponse]
    my_unread_count: int = 0

    @computed_field
    @property
    def status(self) -> str:
        return "archived" if self.is_archived else "active"

    model_config = {"from_attributes": True}


class ThreadBrief(BaseModel):
    """Lightweight thread listing item."""
    id: int
    subject: str
    order_id: int | None
    use_virtual_ids: bool
    is_archived: bool
    participant_count: int
    last_message_at: datetime | None
    my_unread_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class VirtualContactResponse(BaseModel):
    """Returns the virtual alias the caller has in a specific thread."""
    thread_id: int
    user_id: int
    virtual_contact_id: str | None
    message: str
