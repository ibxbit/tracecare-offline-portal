"""
Reviews & Moderation Module
============================
Handles review submission, image uploads, follow-ups, credibility scoring,
and moderator actions (pin / collapse / delete).  All data persisted offline.

Submission rules (enforced here)
---------------------------------
1. The reviewer must be the customer who placed the order.
2. Anti-spam: only 1 review per order within a 10-minute window.
3. Follow-ups: one follow-up per initial review, within 14 days.
4. Images: max 6 per review, image MIME types only, max 5 MB each.

Credibility weights
-------------------
  Verified order (completed):     base 1.0
  Unverified order (not completed): base 0.7
  Follow-up multiplier:           × 0.5
  Rapid-repeat penalty (<10 min): − 0.2
  Clamped to [0.0, 1.0]

Moderation (admin / catalog_manager)
--------------------------------------
  pin / unpin   — surfaces review at top of per-store listings
  collapse / uncollapse — soft-hides body from public view
  delete        — admin only, hard delete

RBAC
----
  Submit, follow-up, upload images: authenticated end_user (own orders only)
  Moderate: admin, catalog_manager
  Read: all authenticated
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import (
    APIRouter, Depends, File, HTTPException, Query,
    UploadFile, status,
)
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.core.dependencies import get_current_user, require_role
from app.core.file_utils import ValidationError, validate_upload
from app.core.review_credibility import recompute_and_save
from app.database import get_db
from app.models.order import Order, OrderStatus
from app.models.review import (
    MAX_REVIEW_IMAGES,
    REVIEW_RATE_LIMIT_MINUTES,
    FOLLOWUP_WINDOW_DAYS,
    Review,
    ReviewImage,
    ReviewSubjectType,
)
from app.models.user import User, UserRole
from app.schemas.review import (
    ModerationCollapseRequest,
    ModerationPinRequest,
    ReviewCreate,
    ReviewFollowupCreate,
    ReviewImageResponse,
    ReviewResponse,
    ReviewSortDir,
    ReviewSortField,
    ReviewSummary,
)

router = APIRouter(prefix="/reviews", tags=["reviews"])

_MODERATORS = ("admin", "catalog_manager")

# Only image MIME types are accepted for review images
_REVIEW_IMAGE_MIMES = {"image/jpeg", "image/png"}
_MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_review_or_404(db: Session, review_id: int, *, load_images: bool = False) -> Review:
    q = select(Review).where(Review.id == review_id)
    if load_images:
        q = q.options(
            selectinload(Review.images),
            selectinload(Review.followup_reviews),
        )
    review = db.execute(q).scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    return review


def _get_order_or_404(db: Session, order_id: int) -> Order:
    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found",
        )
    return order


def _assert_order_owner(order: Order, current_user: User) -> None:
    if order.customer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only review orders that belong to you",
        )


def _assert_order_completed(order: Order) -> None:
    """
    Enforce the 'review only after completed order' rule.

    Canonical rule: order.status must equal OrderStatus.completed.
    The is_completed boolean mirrors this state but status is the authoritative field.
    """
    if order.status != OrderStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Reviews can only be submitted for completed orders "
                f"(current status: {order.status.value})"
            ),
        )


def _check_antispam(db: Session, reviewer_id: int, order_id: int) -> None:
    """Raise 429 if a review on this order was submitted within the rate-limit window."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=REVIEW_RATE_LIMIT_MINUTES)
    recent = db.execute(
        select(func.count(Review.id)).where(
            Review.reviewer_id == reviewer_id,
            Review.order_id == order_id,
            Review.submitted_at >= cutoff,
        )
    ).scalar_one()
    if recent > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"You already submitted a review for this order within the last "
                f"{REVIEW_RATE_LIMIT_MINUTES} minutes. Please wait before submitting again."
            ),
        )


def _review_image_dir(review_id: int) -> Path:
    d = settings.review_images_path / str(review_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _to_response(review: Review, db: Session) -> ReviewResponse:
    followup_count = db.execute(
        select(func.count(Review.id)).where(Review.parent_review_id == review.id)
    ).scalar_one()
    return ReviewResponse(
        id=review.id,
        order_id=review.order_id,
        reviewer_id=review.reviewer_id,
        subject_type=review.subject_type,
        subject_id=review.subject_id,
        subject_text=review.subject_text,
        rating=review.rating,
        comment=review.comment,
        tags=review.tags,
        is_followup=review.is_followup,
        parent_review_id=review.parent_review_id,
        followup_deadline=review.followup_deadline,
        credibility_score=float(review.credibility_score),
        is_pinned=review.is_pinned,
        is_collapsed=review.is_collapsed,
        store_id=review.store_id,
        moderation_note=review.moderation_note,
        moderated_by=review.moderated_by,
        moderated_at=review.moderated_at,
        submitted_at=review.submitted_at,
        created_at=review.created_at,
        images=[ReviewImageResponse.model_validate(img) for img in review.images],
        followup_count=followup_count,
    )


# ---------------------------------------------------------------------------
# Submission endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def submit_review(
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit an initial review for an order.

    Rules:
    - The order must be in `completed` status (prompt requirement).
    - You must be the customer who placed the order.
    - Anti-spam: one submission per order per 10 minutes.
    - Each order can have multiple reviews (one per subject), but never
      two reviews of the same subject_type+subject_id on the same order
      from the same reviewer.
    """
    order = _get_order_or_404(db, payload.order_id)
    _assert_order_owner(order, current_user)
    _assert_order_completed(order)
    _check_antispam(db, current_user.id, payload.order_id)

    # Prevent duplicate initial reviews for the same subject on the same order
    existing = db.execute(
        select(Review).where(
            Review.reviewer_id == current_user.id,
            Review.order_id == payload.order_id,
            Review.subject_type == payload.subject_type,
            Review.subject_id == payload.subject_id,
            Review.is_followup == False,  # noqa: E712
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"You already reviewed this subject on order {payload.order_id} "
                f"(review id={existing.id}). "
                "Use POST /reviews/{id}/followup to add a follow-up."
            ),
        )

    now = datetime.now(timezone.utc)
    tags_json = json.dumps(payload.tags) if payload.tags is not None else None

    review = Review(
        order_id=payload.order_id,
        reviewer_id=current_user.id,
        subject_type=payload.subject_type,
        subject_id=payload.subject_id,
        subject_text=payload.subject_text,
        rating=payload.rating,
        comment=payload.comment,
        tags=tags_json,
        is_followup=False,
        parent_review_id=None,
        followup_deadline=None,
        store_id=payload.store_id,
        submitted_at=now,
        credibility_score=0.0,  # will be computed below after flush
    )
    db.add(review)
    db.flush()  # get review.id + loads review.order lazily

    recompute_and_save(review, db)
    db.commit()
    db.refresh(review)
    return _to_response(review, db)


@router.post("/{review_id}/followup", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def submit_followup(
    review_id: int,
    payload: ReviewFollowupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit a follow-up review on an existing initial review.

    Rules:
    - The underlying order must still be in `completed` status.
    - Only the original reviewer may add a follow-up.
    - One follow-up per initial review (not per order).
    - Must be submitted within 14 days of the parent review.
    - Anti-spam applies: 10-minute gap from any other review on the same order.
    """
    parent = _get_review_or_404(db, review_id, load_images=False)

    if parent.reviewer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the original reviewer can add a follow-up",
        )
    if parent.is_followup:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot create a follow-up on a follow-up review",
        )

    # Enforce completed-order rule for follow-ups as well
    followup_order = _get_order_or_404(db, parent.order_id)
    _assert_order_completed(followup_order)

    # Check 14-day window
    deadline = parent.created_at + timedelta(days=FOLLOWUP_WINDOW_DAYS)
    now = datetime.now(timezone.utc)
    if now > deadline:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"The 14-day follow-up window for this review closed on "
                f"{deadline.strftime('%Y-%m-%d %H:%M UTC')}."
            ),
        )

    # Check that no follow-up exists yet
    existing_followup = db.execute(
        select(Review).where(
            Review.parent_review_id == review_id,
            Review.is_followup == True,  # noqa: E712
        )
    ).scalar_one_or_none()
    if existing_followup:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A follow-up already exists for this review (id={existing_followup.id})",
        )

    _check_antispam(db, current_user.id, parent.order_id)

    tags_json = json.dumps(payload.tags) if payload.tags is not None else None

    followup = Review(
        order_id=parent.order_id,
        reviewer_id=current_user.id,
        subject_type=parent.subject_type,
        subject_id=parent.subject_id,
        subject_text=parent.subject_text,
        rating=payload.rating,
        comment=payload.comment,
        tags=tags_json,
        is_followup=True,
        parent_review_id=parent.id,
        followup_deadline=deadline,
        store_id=parent.store_id,
        submitted_at=now,
        credibility_score=0.0,
    )
    db.add(followup)
    db.flush()

    recompute_and_save(followup, db)
    db.commit()
    db.refresh(followup)
    return _to_response(followup, db)


# ---------------------------------------------------------------------------
# Image upload/download
# ---------------------------------------------------------------------------

@router.post(
    "/{review_id}/images",
    response_model=ReviewImageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_review_image(
    review_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Attach an image to a review (max 6 per review, images only, ≤ 5 MB).
    Only the reviewer or a moderator may upload images.
    """
    review = _get_review_or_404(db, review_id, load_images=True)

    # Only the reviewer (or a moderator) can upload
    if (review.reviewer_id != current_user.id
            and current_user.role.value not in _MODERATORS):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Enforce image cap
    current_count = len(review.images)
    if current_count >= MAX_REVIEW_IMAGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Reviews may have at most {MAX_REVIEW_IMAGES} images (currently {current_count})",
        )

    data = await file.read()
    declared_mime = file.content_type or "image/jpeg"
    original_filename = file.filename or "image"

    try:
        fingerprint = validate_upload(
            data=data,
            declared_mime=declared_mime,
            original_filename=original_filename,
            allowed_mimes=_REVIEW_IMAGE_MIMES,
            max_size_bytes=_MAX_IMAGE_BYTES,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    suffix = Path(original_filename).suffix.lower() or ".jpg"
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    dest = _review_image_dir(review_id) / stored_name
    dest.write_bytes(data)

    img = ReviewImage(
        review_id=review_id,
        original_filename=original_filename,
        stored_filename=stored_name,
        mime_type=declared_mime.split(";")[0].strip().lower(),
        file_size=fingerprint.size_bytes,
        sha256_fingerprint=fingerprint.sha256,
    )
    db.add(img)
    db.commit()
    db.refresh(img)
    return img


@router.get("/{review_id}/images/{image_id}/download")
def download_review_image(
    review_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Stream a review image from the local filesystem."""
    img = db.execute(
        select(ReviewImage).where(
            ReviewImage.id == image_id,
            ReviewImage.review_id == review_id,
        )
    ).scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    file_path = settings.review_images_path / str(review_id) / img.stored_filename
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image file missing from disk",
        )
    return FileResponse(path=str(file_path), media_type=img.mime_type, filename=img.original_filename)


@router.delete("/{review_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review_image(
    review_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove an image from a review (reviewer or moderator only)."""
    review = _get_review_or_404(db, review_id)
    img = db.execute(
        select(ReviewImage).where(
            ReviewImage.id == image_id,
            ReviewImage.review_id == review_id,
        )
    ).scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    if (review.reviewer_id != current_user.id
            and current_user.role.value not in _MODERATORS):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    file_path = settings.review_images_path / str(review_id) / img.stored_filename
    file_path.unlink(missing_ok=True)

    db.delete(img)
    db.commit()


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ReviewResponse])
def list_reviews(
    subject_type: ReviewSubjectType | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    subject_text: str | None = Query(default=None, max_length=255),
    store_id: str | None = Query(default=None, max_length=100),
    order_id: int | None = Query(default=None),
    reviewer_id: int | None = Query(default=None),
    rating_min: int | None = Query(default=None, ge=1, le=5),
    rating_max: int | None = Query(default=None, ge=1, le=5),
    include_collapsed: bool = Query(
        default=False,
        description="Include collapsed (moderated-hidden) reviews. Moderators only.",
    ),
    followups_only: bool = Query(default=False),
    sort_by: ReviewSortField = Query(default=ReviewSortField.created_at),
    sort_dir: ReviewSortDir = Query(default=ReviewSortDir.desc),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List reviews with multi-criteria filtering.

    Collapsed reviews are hidden from end-users by default.
    Pass include_collapsed=true (requires admin/catalog_manager role) to see them.
    Pinned reviews are always included; use sort_by=pinned_first to surface them.
    """
    # Only moderators may request collapsed reviews
    if include_collapsed and current_user.role.value not in _MODERATORS:
        include_collapsed = False  # silently downgrade for end-users

    q = (
        select(Review)
        .options(selectinload(Review.images))
    )

    if not include_collapsed:
        q = q.where(Review.is_collapsed == False)  # noqa: E712

    if subject_type is not None:
        q = q.where(Review.subject_type == subject_type)
    if subject_id is not None:
        q = q.where(Review.subject_id == subject_id)
    if subject_text is not None:
        q = q.where(Review.subject_text.ilike(f"%{subject_text}%"))
    if store_id is not None:
        q = q.where(Review.store_id == store_id)
    if order_id is not None:
        q = q.where(Review.order_id == order_id)
    if reviewer_id is not None:
        # End-users can only filter their own reviews
        if current_user.role == UserRole.end_user and reviewer_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        q = q.where(Review.reviewer_id == reviewer_id)
    if rating_min is not None:
        q = q.where(Review.rating >= rating_min)
    if rating_max is not None:
        q = q.where(Review.rating <= rating_max)
    if followups_only:
        q = q.where(Review.is_followup == True)  # noqa: E712

    # Sorting
    if sort_by == ReviewSortField.pinned_first:
        q = q.order_by(Review.is_pinned.desc(), Review.created_at.desc())
    else:
        col = getattr(Review, sort_by.value)
        q = q.order_by(col.asc() if sort_dir == ReviewSortDir.asc else col.desc())

    reviews = db.execute(q.offset(skip).limit(limit)).scalars().all()
    return [_to_response(r, db) for r in reviews]


@router.get("/summary", response_model=ReviewSummary)
def get_review_summary(
    subject_type: ReviewSubjectType = Query(...),
    subject_id: int | None = Query(default=None),
    subject_text: str | None = Query(default=None, max_length=255),
    store_id: str = Query(default="default"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Aggregate statistics (average rating, star distribution, credibility)
    for a given subject within a store scope.
    Collapsed reviews are excluded from aggregates.
    """
    q = select(Review).where(
        Review.subject_type == subject_type,
        Review.is_collapsed == False,  # noqa: E712
        Review.store_id == store_id,
    )
    if subject_id is not None:
        q = q.where(Review.subject_id == subject_id)
    if subject_text is not None:
        q = q.where(Review.subject_text == subject_text)

    reviews = db.execute(q).scalars().all()

    dist: dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    total_rating = 0.0
    total_credibility = 0.0
    verified_count = 0
    has_pinned = False

    for r in reviews:
        dist[r.rating] = dist.get(r.rating, 0) + 1
        total_rating += r.rating
        score = float(r.credibility_score)
        total_credibility += score
        if score >= 1.0:
            verified_count += 1
        if r.is_pinned:
            has_pinned = True

    n = len(reviews)
    return ReviewSummary(
        subject_type=subject_type,
        subject_id=subject_id,
        subject_text=subject_text,
        store_id=store_id,
        total_reviews=n,
        average_rating=round(total_rating / n, 2) if n else None,
        average_credibility=round(total_credibility / n, 3) if n else None,
        rating_distribution=dist,
        verified_review_count=verified_count,
        has_pinned=has_pinned,
    )


@router.get("/{review_id}", response_model=ReviewResponse)
def get_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single review. End-users cannot see collapsed reviews unless they are the author."""
    review = _get_review_or_404(db, review_id, load_images=True)

    if review.is_collapsed:
        is_owner = review.reviewer_id == current_user.id
        is_mod = current_user.role.value in _MODERATORS
        if not is_owner and not is_mod:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This review has been collapsed by a moderator",
            )
    return _to_response(review, db)


# ---------------------------------------------------------------------------
# Moderation endpoints
# ---------------------------------------------------------------------------

@router.patch("/{review_id}/pin", response_model=ReviewResponse)
def pin_review(
    review_id: int,
    payload: ModerationPinRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_MODERATORS)),
):
    """
    Pin a review to the top of its store's listing.
    Pinning is scoped to store_id — a review pinned in 'store-a' will not
    appear pinned in 'store-b'.
    """
    review = _get_review_or_404(db, review_id, load_images=True)
    if review.is_pinned and review.store_id == payload.store_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Review is already pinned")

    review.is_pinned = True
    review.store_id = payload.store_id
    review.moderated_by = current_user.id
    review.moderated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(review)
    return _to_response(review, db)


@router.patch("/{review_id}/unpin", response_model=ReviewResponse)
def unpin_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_MODERATORS)),
):
    """Remove the pin from a review."""
    review = _get_review_or_404(db, review_id, load_images=True)
    if not review.is_pinned:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Review is not pinned")

    review.is_pinned = False
    review.moderated_by = current_user.id
    review.moderated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(review)
    return _to_response(review, db)


@router.patch("/{review_id}/collapse", response_model=ReviewResponse)
def collapse_review(
    review_id: int,
    payload: ModerationCollapseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_MODERATORS)),
):
    """
    Collapse (soft-hide) a review from public listings.
    The review body is preserved in the database; only the moderator and
    the original reviewer can still retrieve it.
    A moderation note explains the reason to staff.
    """
    review = _get_review_or_404(db, review_id, load_images=True)
    if review.is_collapsed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Review is already collapsed")

    review.is_collapsed = True
    review.moderation_note = payload.note
    review.moderated_by = current_user.id
    review.moderated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(review)
    return _to_response(review, db)


@router.patch("/{review_id}/uncollapse", response_model=ReviewResponse)
def uncollapse_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_MODERATORS)),
):
    """Restore a previously collapsed review to public visibility."""
    review = _get_review_or_404(db, review_id, load_images=True)
    if not review.is_collapsed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Review is not collapsed")

    review.is_collapsed = False
    review.moderation_note = None
    review.moderated_by = current_user.id
    review.moderated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(review)
    return _to_response(review, db)


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a review.
    - End-users may delete their own non-collapsed reviews.
    - Admins may delete any review.
    - All images are removed from disk on deletion.
    """
    review = _get_review_or_404(db, review_id, load_images=True)

    is_own = review.reviewer_id == current_user.id
    is_admin = current_user.role == UserRole.admin

    if not is_own and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if not is_admin and review.is_collapsed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Collapsed reviews can only be deleted by an administrator",
        )

    # Remove image files from disk
    img_dir = settings.review_images_path / str(review_id)
    for img in review.images:
        (img_dir / img.stored_filename).unlink(missing_ok=True)
    try:
        img_dir.rmdir()
    except (FileNotFoundError, OSError):
        pass

    db.delete(review)
    db.commit()
