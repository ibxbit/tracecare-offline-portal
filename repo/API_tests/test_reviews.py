"""
API tests for /api/reviews — create, follow-up, moderation, credibility.

Note: Reviews are tied to orders.  Because this test suite does not create
real orders, most tests use the admin account which has broader access, and
we verify HTTP status codes + schema shape rather than business-logic details
that require a full order pipeline.
"""
import uuid
import httpx
import pytest


class TestReviewListAndRead:
    def test_list_reviews_returns_list(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/reviews", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list) or ("items" in body)

    def test_review_summary_available(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/reviews/summary", headers=admin_headers)
        # 200 with stats, or 404 if no subject specified — either is acceptable
        assert resp.status_code in (200, 404, 422)

    def test_get_nonexistent_review_returns_404(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/reviews/999999999", headers=admin_headers)
        assert resp.status_code == 404


class TestReviewCreation:
    def test_create_review_requires_order(self, client: httpx.Client, admin_headers: dict):
        """Without a valid order_id, review creation should be rejected."""
        resp = client.post("/api/reviews", json={
            "order_id": 999999999,
            "subject_type": "product",
            "subject_id": 1,
            "rating": 5,
            "comment": "Great product!",
        }, headers=admin_headers)
        # 404 (order not found) or 403 (not the order owner)
        assert resp.status_code in (400, 403, 404, 422)

    def test_invalid_rating_rejected(self, client: httpx.Client, admin_headers: dict):
        resp = client.post("/api/reviews", json={
            "order_id": 1,
            "subject_type": "product",
            "subject_id": 1,
            "rating": 6,  # out of range
            "comment": "test",
        }, headers=admin_headers)
        assert resp.status_code in (400, 422)

    def test_rating_zero_rejected(self, client: httpx.Client, admin_headers: dict):
        resp = client.post("/api/reviews", json={
            "order_id": 1,
            "subject_type": "product",
            "subject_id": 1,
            "rating": 0,
        }, headers=admin_headers)
        assert resp.status_code in (400, 422)

    def test_comment_too_long_rejected(self, client: httpx.Client, admin_headers: dict):
        resp = client.post("/api/reviews", json={
            "order_id": 1,
            "subject_type": "product",
            "subject_id": 1,
            "rating": 4,
            "comment": "x" * 1001,  # exceeds 1000 char limit
        }, headers=admin_headers)
        assert resp.status_code in (400, 422)


class TestReviewModeration:
    """Moderation endpoints: pin, unpin, collapse, uncollapse, delete."""

    def test_pin_nonexistent_review_returns_404(
        self, client: httpx.Client, admin_headers: dict
    ):
        resp = client.patch("/api/reviews/999999999/pin", headers=admin_headers)
        assert resp.status_code == 404

    def test_collapse_nonexistent_review_returns_404(
        self, client: httpx.Client, admin_headers: dict
    ):
        resp = client.patch(
            "/api/reviews/999999999/collapse",
            json={"note": "spam"},
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_end_user_cannot_pin_review(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.patch("/api/reviews/1/pin", headers=temp_end_user_headers)
        assert resp.status_code in (403, 404)

    def test_end_user_cannot_collapse_review(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.patch(
            "/api/reviews/1/collapse",
            json={"note": "spam"},
            headers=temp_end_user_headers,
        )
        assert resp.status_code in (403, 404)


class TestReviewFiltering:
    def test_filter_by_rating(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/reviews", params={"min_rating": 4}, headers=admin_headers)
        assert resp.status_code == 200

    def test_filter_by_subject_type(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/reviews", params={"subject_type": "product"}, headers=admin_headers)
        assert resp.status_code == 200

    def test_sort_by_credibility(self, client: httpx.Client, admin_headers: dict):
        resp = client.get(
            "/api/reviews",
            params={"sort_by": "credibility_score", "sort_dir": "desc"},
            headers=admin_headers,
        )
        assert resp.status_code == 200

    def test_pagination(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/reviews", params={"skip": 0, "limit": 5}, headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        # Either a direct list or paginated wrapper
        items = body if isinstance(body, list) else body.get("items", [])
        assert len(items) <= 5
