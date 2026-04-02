import enum
from datetime import datetime, timezone, timedelta
from sqlalchemy import (
    String, Text, DateTime, ForeignKey, Integer, Boolean,
    Enum as SAEnum, CheckConstraint, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

# Anti-spam: minimum gap between two reviews on the same order
REVIEW_RATE_LIMIT_MINUTES = 10

# Follow-up window after initial review
FOLLOWUP_WINDOW_DAYS = 14

# Max images per review
MAX_REVIEW_IMAGES = 6

# Max comment length
MAX_COMMENT_LENGTH = 1000


class ReviewSubjectType(str, enum.Enum):
    product = "product"
    exam_type = "exam_type"
    catalog_item = "catalog_item"


class Review(Base):
    """
    Customer/patient review linked to a specific order.

    Submission rules (enforced at application layer):
      - 1–5 star rating
      - comment ≤ 1,000 chars
      - max 6 images (via ReviewImage)
      - follow-up reviews allowed within 14 days of parent, one per order
      - anti-spam: 1 review per order per 10 minutes

    Credibility score (computed and stored at submission time):
      - Verified order (is_completed=True): base weight 1.0
      - Follow-up edit: ×0.5 multiplier
      - Rapid repeat within 10 min on same order: −0.2 penalty
      - Clamped to [0.0, 1.0]

    Moderation fields:
      - is_pinned: surfaces the review at the top of listings
      - is_collapsed: hides the review body from public listings (soft-hide)
      - store_id: allows per-store sorting / moderation scopes
    """
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Every review must be tied to an order
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id"), nullable=False, index=True
    )
    reviewer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )

    # What is being reviewed
    subject_type: Mapped[ReviewSubjectType] = mapped_column(
        SAEnum(ReviewSubjectType), nullable=False
    )
    subject_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subject_text: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Review content
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(MAX_COMMENT_LENGTH), nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON array stored as text

    # Follow-up support
    is_followup: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parent_review_id: Mapped[int | None] = mapped_column(
        ForeignKey("reviews.id"), nullable=True
    )
    followup_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # parent.created_at + 14 days; NULL on initial reviews

    # Anti-spam tracking
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Credibility score — persisted so listing sorts don't need recomputation
    credibility_score: Mapped[float] = mapped_column(
        Numeric(4, 3), nullable=False, default=0.0
    )

    # Moderation
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_collapsed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    store_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default", index=True)
    moderation_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    moderated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    order = relationship("Order", back_populates="reviews")
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    moderator = relationship("User", foreign_keys=[moderated_by])
    parent_review = relationship("Review", remote_side="Review.id", foreign_keys=[parent_review_id])
    followup_reviews = relationship(
        "Review",
        foreign_keys="[Review.parent_review_id]",
        back_populates="parent_review",
    )
    images = relationship(
        "ReviewImage",
        back_populates="review",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_reviews_rating_range"),
        CheckConstraint(
            "credibility_score >= 0.0 AND credibility_score <= 1.0",
            name="ck_reviews_credibility_range",
        ),
    )


class ReviewImage(Base):
    """
    Image attachment for a review. Maximum 6 per review (enforced at app layer).
    Stores original filename, MIME type, size, and SHA-256 fingerprint.
    """
    __tablename__ = "review_images"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    review_id: Mapped[int] = mapped_column(
        ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True
    )

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(500), nullable=False)   # UUID-based on disk
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)         # image/jpeg, image/png…
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)             # bytes
    sha256_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False) # hex digest

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    review = relationship("Review", back_populates="images")

    __table_args__ = (
        CheckConstraint("file_size > 0", name="ck_review_images_size_positive"),
    )
