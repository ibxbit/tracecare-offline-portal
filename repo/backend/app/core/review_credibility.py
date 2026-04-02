"""
Review Credibility Engine
==========================
Computes a deterministic credibility score in [0.0, 1.0] for every review.
The score is persisted on the Review row at submission time so listing
queries can sort by it without re-computing.

Scoring rules
-------------
1. Base weight
   - Order is completed (verified purchase): 1.0
   - Order exists but is not yet completed:  0.7

2. Follow-up multiplier
   - is_followup=True: score × 0.5
   (A follow-up adds context but carries less independent weight than an
   original review, since the reviewer has already had their say.)

3. Rapid-repeat penalty
   - If the *same reviewer* already submitted another review on the *same order*
     within the preceding REVIEW_RATE_LIMIT_MINUTES (10 min), subtract 0.2.
   - This deters gaming a subject's average rating by flooding with quick reviews.

4. Clamping
   - Final score is clamped to [0.0, 1.0] and rounded to 3 decimal places.

The function is pure with respect to the database: it receives the already-
committed Review object and a db Session, then queries for the rapid-repeat
count.  It does NOT commit — callers are responsible for persisting the result.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.review import Review, REVIEW_RATE_LIMIT_MINUTES


def compute_credibility(review: Review, db: Session) -> float:
    """
    Return the credibility score for *review*.

    Assumptions:
    - review.order relationship is loaded (or will trigger a lazy load).
    - review.submitted_at is set.
    - The review row itself is already in the session (id is available).
    """
    # 1. Base weight from order verification status
    order = review.order
    score: float = 1.0 if (order and order.is_completed) else 0.7

    # 2. Follow-up multiplier
    if review.is_followup:
        score *= 0.5

    # 3. Rapid-repeat penalty
    #    Count other reviews by this reviewer on the same order submitted
    #    within the rate-limit window *before* this submission.
    window_start = review.submitted_at - timedelta(minutes=REVIEW_RATE_LIMIT_MINUTES)
    rapid_count: int = db.execute(
        select(func.count(Review.id)).where(
            Review.reviewer_id == review.reviewer_id,
            Review.order_id == review.order_id,
            Review.id != review.id,           # exclude the review being scored
            Review.submitted_at >= window_start,
            Review.submitted_at <= review.submitted_at,
        )
    ).scalar_one()

    if rapid_count > 0:
        score -= 0.2

    # 4. Clamp and round
    return round(max(0.0, min(1.0, score)), 3)


def recompute_and_save(review: Review, db: Session) -> float:
    """Convenience: compute, persist on the review, return the score."""
    score = compute_credibility(review, db)
    review.credibility_score = score
    return score
