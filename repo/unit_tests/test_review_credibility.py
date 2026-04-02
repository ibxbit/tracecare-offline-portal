"""
Unit tests for app.core.review_credibility.compute_credibility.

Scoring rules (from module docstring):
  Base weight: is_completed → 1.0 | not completed → 0.7
  Follow-up:   × 0.5
  Rapid-repeat (same reviewer, same order, within 10 min): −0.2
  Clamped to [0.0, 1.0], rounded to 3 decimal places.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.core.review_credibility import compute_credibility


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_review(
    is_completed: bool = True,
    is_followup: bool = False,
    rapid_count: int = 0,
    reviewer_id: int = 1,
    order_id: int = 1,
    review_id: int = 1,
) -> tuple:
    """Return (review_mock, db_mock) with the given scenario parameters."""
    order = MagicMock()
    order.is_completed = is_completed

    review = MagicMock()
    review.order = order
    review.is_followup = is_followup
    review.submitted_at = datetime.now(timezone.utc)
    review.reviewer_id = reviewer_id
    review.order_id = order_id
    review.id = review_id

    db = MagicMock()
    db.execute.return_value.scalar_one.return_value = rapid_count

    return review, db


# ---------------------------------------------------------------------------
# Base weight
# ---------------------------------------------------------------------------

class TestBaseWeight:
    def test_verified_order_base_score_1_0(self):
        review, db = _make_review(is_completed=True)
        assert compute_credibility(review, db) == 1.0

    def test_unverified_order_base_score_0_7(self):
        review, db = _make_review(is_completed=False)
        assert compute_credibility(review, db) == 0.7

    def test_no_order_relationship_defaults_to_unverified(self):
        review, db = _make_review()
        review.order = None  # no order loaded
        score = compute_credibility(review, db)
        assert score == 0.7


# ---------------------------------------------------------------------------
# Follow-up multiplier
# ---------------------------------------------------------------------------

class TestFollowupMultiplier:
    def test_verified_followup(self):
        review, db = _make_review(is_completed=True, is_followup=True)
        # 1.0 * 0.5 = 0.5
        assert compute_credibility(review, db) == 0.5

    def test_unverified_followup(self):
        review, db = _make_review(is_completed=False, is_followup=True)
        # 0.7 * 0.5 = 0.35
        assert compute_credibility(review, db) == 0.35

    def test_non_followup_unaffected(self):
        review, db = _make_review(is_completed=True, is_followup=False)
        assert compute_credibility(review, db) == 1.0


# ---------------------------------------------------------------------------
# Rapid-repeat penalty
# ---------------------------------------------------------------------------

class TestRapidRepeatPenalty:
    def test_no_rapid_repeat_no_penalty(self):
        review, db = _make_review(is_completed=True, rapid_count=0)
        assert compute_credibility(review, db) == 1.0

    def test_one_rapid_repeat_subtracts_0_2_verified(self):
        review, db = _make_review(is_completed=True, rapid_count=1)
        # 1.0 - 0.2 = 0.8
        assert compute_credibility(review, db) == 0.8

    def test_one_rapid_repeat_subtracts_0_2_unverified(self):
        review, db = _make_review(is_completed=False, rapid_count=1)
        # 0.7 - 0.2 = 0.5
        assert compute_credibility(review, db) == 0.5

    def test_multiple_rapid_repeats_only_one_penalty(self):
        # Penalty is binary (any rapid_count > 0 → subtract 0.2 once)
        r1, db1 = _make_review(is_completed=True, rapid_count=1)
        r2, db2 = _make_review(is_completed=True, rapid_count=3)
        assert compute_credibility(r1, db1) == compute_credibility(r2, db2)


# ---------------------------------------------------------------------------
# Combined scenarios
# ---------------------------------------------------------------------------

class TestCombinedScoring:
    def test_verified_followup_with_rapid_repeat(self):
        review, db = _make_review(is_completed=True, is_followup=True, rapid_count=1)
        # 1.0 * 0.5 - 0.2 = 0.3
        assert compute_credibility(review, db) == 0.3

    def test_unverified_followup_with_rapid_repeat(self):
        review, db = _make_review(is_completed=False, is_followup=True, rapid_count=1)
        # 0.7 * 0.5 - 0.2 = 0.35 - 0.2 = 0.15
        assert compute_credibility(review, db) == 0.15


# ---------------------------------------------------------------------------
# Clamping and rounding
# ---------------------------------------------------------------------------

class TestClampingAndRounding:
    def test_score_never_below_zero(self):
        review, db = _make_review(is_completed=False, is_followup=True, rapid_count=1)
        score = compute_credibility(review, db)
        assert score >= 0.0

    def test_score_never_above_one(self):
        review, db = _make_review(is_completed=True, is_followup=False, rapid_count=0)
        score = compute_credibility(review, db)
        assert score <= 1.0

    def test_score_rounded_to_3_decimal_places(self):
        review, db = _make_review(is_completed=False, is_followup=True)
        score = compute_credibility(review, db)
        # 0.7 * 0.5 = 0.35 — already 2 dp, but check it doesn't exceed 3
        assert score == round(score, 3)

    def test_all_scores_in_valid_range(self):
        scenarios = [
            (True, False, 0),
            (True, False, 1),
            (True, True, 0),
            (True, True, 1),
            (False, False, 0),
            (False, False, 1),
            (False, True, 0),
            (False, True, 1),
        ]
        for is_completed, is_followup, rapid in scenarios:
            review, db = _make_review(is_completed=is_completed, is_followup=is_followup, rapid_count=rapid)
            score = compute_credibility(review, db)
            assert 0.0 <= score <= 1.0, f"Score {score} out of range for scenario {(is_completed, is_followup, rapid)}"
