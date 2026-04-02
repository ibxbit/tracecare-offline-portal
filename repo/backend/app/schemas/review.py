from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.review import ReviewSubjectType, MAX_COMMENT_LENGTH, MAX_REVIEW_IMAGES


# ---------------------------------------------------------------------------
# Sorting / listing helpers
# ---------------------------------------------------------------------------

class ReviewSortField(str, Enum):
    created_at = "created_at"
    rating = "rating"
    credibility_score = "credibility_score"
    pinned_first = "pinned_first"   # is_pinned DESC, then created_at DESC


class ReviewSortDir(str, Enum):
    asc = "asc"
    desc = "desc"


# ---------------------------------------------------------------------------
# Submission
# ---------------------------------------------------------------------------

class ReviewCreate(BaseModel):
    order_id: int
    subject_type: ReviewSubjectType
    subject_id: int | None = Field(
        default=None,
        description="ID of the product or catalog item being reviewed",
    )
    subject_text: str | None = Field(
        default=None,
        max_length=255,
        description="Human-readable label for exam_type subjects",
    )
    rating: Annotated[int, Field(ge=1, le=5)]
    comment: str | None = Field(default=None, max_length=MAX_COMMENT_LENGTH)
    tags: list[str] | None = Field(
        default=None,
        description="Optional free-form tags, e.g. ['fast-delivery', 'fresh']",
    )
    store_id: str = Field(default="default", max_length=100)

    @model_validator(mode="after")
    def subject_consistency(self) -> ReviewCreate:
        if self.subject_type == ReviewSubjectType.exam_type:
            if not self.subject_text:
                raise ValueError("subject_text is required for exam_type reviews")
        else:
            if self.subject_id is None:
                raise ValueError(
                    f"subject_id is required for {self.subject_type.value} reviews"
                )
        return self

    @field_validator("tags", mode="before")
    @classmethod
    def coerce_tags(cls, v: object) -> list[str] | None:
        """Accept either a list[str] or a JSON-encoded string."""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if not isinstance(parsed, list):
                    raise ValueError("tags must be a JSON array")
                return parsed
            except json.JSONDecodeError as exc:
                raise ValueError(f"tags is not valid JSON: {exc}") from exc
        return v


class ReviewFollowupCreate(BaseModel):
    rating: Annotated[int, Field(ge=1, le=5)]
    comment: str | None = Field(default=None, max_length=MAX_COMMENT_LENGTH)
    tags: list[str] | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def coerce_tags(cls, v: object) -> list[str] | None:
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError as exc:
                raise ValueError(f"tags is not valid JSON: {exc}") from exc
        return v


# ---------------------------------------------------------------------------
# Moderation requests
# ---------------------------------------------------------------------------

class ModerationCollapseRequest(BaseModel):
    note: str | None = Field(
        default=None,
        max_length=500,
        description="Reason for collapsing; displayed to staff, not to the public",
    )


class ModerationPinRequest(BaseModel):
    store_id: str = Field(default="default", max_length=100,
                           description="Pin the review within this store scope")


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class ReviewImageResponse(BaseModel):
    id: int
    review_id: int
    original_filename: str
    mime_type: str
    file_size: int
    sha256_fingerprint: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewResponse(BaseModel):
    id: int
    order_id: int
    reviewer_id: int

    subject_type: ReviewSubjectType
    subject_id: int | None
    subject_text: str | None

    rating: int
    comment: str | None
    tags: list[str] | None = None

    is_followup: bool
    parent_review_id: int | None
    followup_deadline: datetime | None

    credibility_score: float

    is_pinned: bool
    is_collapsed: bool
    store_id: str
    moderation_note: str | None
    moderated_by: int | None
    moderated_at: datetime | None

    submitted_at: datetime
    created_at: datetime

    images: list[ReviewImageResponse] = []
    followup_count: int = 0

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def deserialize_tags(self) -> ReviewResponse:
        """tags is stored as a JSON string in the DB; expose as list."""
        if isinstance(self.tags, str):
            try:
                self.tags = json.loads(self.tags)
            except (json.JSONDecodeError, TypeError):
                self.tags = []
        return self


class ReviewSummary(BaseModel):
    """Aggregate statistics for a subject (product, catalog item, exam type)."""
    subject_type: ReviewSubjectType
    subject_id: int | None
    subject_text: str | None
    store_id: str

    total_reviews: int
    average_rating: float | None       # None when total_reviews == 0
    average_credibility: float | None
    rating_distribution: dict[int, int]  # {1: n, 2: n, 3: n, 4: n, 5: n}
    verified_review_count: int          # reviews with credibility_score >= 1.0
    has_pinned: bool
