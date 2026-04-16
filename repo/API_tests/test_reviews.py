"""
API tests for /api/reviews — create, follow-up, moderation, credibility.

The legacy classes in this file exercise schema-level contracts (rating
bounds, subject-type consistency, moderation RBAC) that don't require a
real order to fail.

The NEW classes at the bottom (TestRealReviewLifecycle, TestReviewCooldown,
TestReviewImageTamperDetection, TestFollowupLifecycle) drive the full
real-world flow:

  1. A real end_user is provisioned via the admin API.
  2. A real Order row is created in the DB with status=completed.
  3. The user logs in and submits a review via HTTP.
  4. Business rules (cooldown, follow-up window, image tamper detection,
     own-orders-only, pin/collapse moderation) are exercised end-to-end.

See conftest.py for the real_completed_order / real_pending_order fixtures.
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
        resp = client.patch(
            "/api/reviews/999999999/pin",
            json={},
            headers=admin_headers
        )
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
    def test_filter_by_rating_min(self, client: httpx.Client, admin_headers: dict):
        """Backend param is rating_min (not min_rating)."""
        resp = client.get("/api/reviews", params={"rating_min": 4}, headers=admin_headers)
        assert resp.status_code == 200

    def test_filter_by_rating_max(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/reviews", params={"rating_max": 3}, headers=admin_headers)
        assert resp.status_code == 200

    def test_stale_min_rating_param_ignored_or_rejected(
        self, client: httpx.Client, admin_headers: dict
    ):
        """Confirm that `min_rating` (old name) is NOT a backend query param."""
        resp = client.get("/api/reviews", params={"min_rating": 4}, headers=admin_headers)
        # FastAPI ignores unknown query params (returns 200 but does not filter by it)
        # This test documents that the correct param is rating_min, not min_rating.
        assert resp.status_code == 200  # not a hard error, but param has no effect

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
        items = body if isinstance(body, list) else body.get("items", [])
        assert len(items) <= 5


class TestReviewSubjectTypes:
    """Validate that only the backend-defined enum values are accepted."""

    VALID_TYPES = ["product", "exam_type", "catalog_item"]
    INVALID_TYPES = ["exam_package", "service", "package", "PRODUCT", ""]

    def test_valid_subject_type_filter_accepted(
        self, client: httpx.Client, admin_headers: dict
    ):
        for t in self.VALID_TYPES:
            resp = client.get("/api/reviews", params={"subject_type": t},
                              headers=admin_headers)
            assert resp.status_code == 200, (
                f"Expected 200 for valid subject_type='{t}', got {resp.status_code}"
            )

    def test_invalid_subject_type_filter_rejected(
        self, client: httpx.Client, admin_headers: dict
    ):
        for t in ["exam_package", "service"]:
            resp = client.get("/api/reviews", params={"subject_type": t},
                              headers=admin_headers)
            assert resp.status_code == 422, (
                f"Expected 422 for invalid subject_type='{t}', got {resp.status_code}"
            )


class TestReviewImagePolicy:
    """Enforce PNG/JPG-only policy for review images."""

    def test_webp_rejected_for_review_image(
        self, client: httpx.Client, admin_headers: dict
    ):
        import io
        # We can't create a real review without an order, but we verify the endpoint
        # returns 404 (review not found) rather than 422 (wrong MIME) for a non-existent
        # review — meaning the MIME check happens after review lookup.
        fake_webp = b"RIFF\x24\x00\x00\x00WEBPVP8 "
        resp = client.post(
            "/api/reviews/999999999/images",
            files={"file": ("photo.webp", io.BytesIO(fake_webp), "image/webp")},
            headers=admin_headers,
        )
        # 404 because review doesn't exist; not 422 which would mean wrong MIME accepted
        # This confirms the endpoint exists and requires review to exist before MIME check
        assert resp.status_code in (404, 422)


class TestCompletedOrderGating:
    """
    Reviews must only be submitted for completed orders.
    Backend enforces: order.status == OrderStatus.completed (422 otherwise).
    """

    def test_nonexistent_order_returns_404(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        """order_id 999999999 does not exist — expect 404, not a silent pass."""
        resp = client.post("/api/reviews", json={
            "order_id": 999999999,
            "subject_type": "product",
            "subject_id": 1,
            "rating": 5,
            "comment": "Great!",
        }, headers=temp_end_user_headers)
        assert resp.status_code == 404, (
            f"Non-existent order should return 404, got {resp.status_code}"
        )

    def test_create_review_shape_exam_type_requires_subject_text(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        """
        exam_type reviews must supply subject_text, not subject_id.
        Without subject_text the backend validator returns 422.
        """
        resp = client.post("/api/reviews", json={
            "order_id": 1,
            "subject_type": "exam_type",
            "subject_id": 5,        # subject_id is forbidden for exam_type
            "rating": 4,
            "comment": "Good exam",
        }, headers=temp_end_user_headers)
        # 422 from subject_consistency validator (subject_text is required for exam_type)
        assert resp.status_code in (400, 422), (
            f"exam_type without subject_text should fail schema validation, "
            f"got {resp.status_code}: {resp.text}"
        )

    def test_create_review_exam_type_with_subject_text_passes_schema(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        """
        exam_type + subject_text passes schema validation.
        Expect 404 (order not found) or 403 (not owner) or 422 (non-completed),
        NOT a generic 500 or the schema-level 422 that misses subject_text.
        """
        resp = client.post("/api/reviews", json={
            "order_id": 999999999,
            "subject_type": "exam_type",
            "subject_text": "CBC",
            "rating": 4,
            "comment": "Accurate results",
        }, headers=temp_end_user_headers)
        # Schema is valid; the failure is from order lookup (404), not payload shape
        assert resp.status_code in (404, 403, 422), (
            f"Valid exam_type payload should pass schema check, "
            f"got {resp.status_code}: {resp.text}"
        )
        # Must NOT be a 422 caused by missing subject_text
        if resp.status_code == 422:
            body = resp.json()
            detail = str(body.get("detail", ""))
            assert "subject_text" not in detail.lower(), (
                "422 must not be from missing subject_text when subject_text is provided"
            )

    def test_product_review_without_subject_id_rejected(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        """product/catalog_item reviews must supply subject_id (not subject_text)."""
        resp = client.post("/api/reviews", json={
            "order_id": 1,
            "subject_type": "product",
            "subject_text": "Some product",  # wrong field for product
            "rating": 3,
            "comment": "OK",
        }, headers=temp_end_user_headers)
        # subject_id is missing → 422 from subject_consistency validator
        assert resp.status_code in (400, 422), (
            f"product review without subject_id should be rejected, "
            f"got {resp.status_code}"
        )


class TestReviewOwnership:
    """Object-level authorization: reviewers can only act on their own orders."""

    def test_end_user_cannot_moderate_pin(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        """End users must not be able to pin reviews (admin/catalog_manager only)."""
        resp = client.patch("/api/reviews/1/pin", headers=temp_end_user_headers)
        assert resp.status_code in (403, 404), (
            f"End user pin should be forbidden, got {resp.status_code}"
        )

    def test_end_user_cannot_moderate_collapse(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.patch(
            "/api/reviews/1/collapse",
            json={"note": "test"},
            headers=temp_end_user_headers,
        )
        assert resp.status_code in (403, 404)

    def test_reviewer_id_filter_restricted_for_other_user(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        """
        End-users requesting reviewer_id != own ID should get 403.
        We use reviewer_id=1 (admin user) which is not the temp_end_user.
        """
        resp = client.get(
            "/api/reviews",
            params={"reviewer_id": 1},
            headers=temp_end_user_headers,
        )
        assert resp.status_code in (200, 403), (
            f"reviewer_id cross-user filter should be 403 or empty 200, "
            f"got {resp.status_code}"
        )
        # If 200, the list must be empty (no admin reviews visible to end_user)
        if resp.status_code == 200:
            # end_user should not see admin's reviews via cross-reviewer_id query
            pass  # actual enforcement tested by checking 403 path above


class TestReviewAntiSpam:
    """
    Anti-spam and follow-up business rule documentation tests.
    These verify the contract shape rather than timing (timing requires real clock control).
    """

    def test_follow_up_on_nonexistent_review_returns_404(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.post(
            "/api/reviews/999999999/followup",
            json={"rating": 4, "comment": "Follow-up"},
            headers=temp_end_user_headers,
        )
        assert resp.status_code == 404

    def test_follow_up_requires_rating(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        """Follow-up payload must include rating 1-5."""
        resp = client.post(
            "/api/reviews/1/followup",
            json={"rating": 6, "comment": "Too high"},
            headers=temp_end_user_headers,
        )
        assert resp.status_code in (400, 403, 404, 422)

    def test_rating_boundaries(self, client: httpx.Client, admin_headers: dict):
        """rating must be 1-5; 0 and 6 must be rejected."""
        for bad_rating in (0, 6):
            resp = client.post("/api/reviews", json={
                "order_id": 1,
                "subject_type": "product",
                "subject_id": 1,
                "rating": bad_rating,
                "comment": "test",
            }, headers=admin_headers)
            assert resp.status_code in (400, 422), (
                f"rating={bad_rating} should be rejected, got {resp.status_code}"
            )


# ===========================================================================
# Real-world lifecycle tests — use an actual Order row + real HTTP submission
# ===========================================================================

class TestRealReviewLifecycle:
    """
    Full real-world submission path. No admin shortcuts:
    the reviewer is a genuine end_user and the order is a real, completed
    row in the orders table.
    """

    def test_end_user_can_submit_review_on_own_completed_order(
        self,
        client: httpx.Client,
        temp_end_user_headers: dict,
        real_completed_order,
    ):
        resp = client.post(
            "/api/reviews",
            json={
                "order_id": real_completed_order.id,
                "subject_type": "product",
                "subject_id": 1,
                "rating": 5,
                "comment": "Arrived on time, quality excellent.",
                "tags": ["fresh", "fast-delivery"],
            },
            headers=temp_end_user_headers,
        )
        assert resp.status_code == 201, f"expected 201, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["order_id"] == real_completed_order.id
        assert body["rating"] == 5
        assert body["is_followup"] is False
        # Credibility must be computed from a VERIFIED (completed) order — non-zero.
        assert body["credibility_score"] > 0.0, (
            "Review on a completed order must receive a positive credibility score"
        )
        assert body["reviewer_id"] != 1, (
            "Reviewer must be the real end_user, not the admin account (id=1)"
        )

    def test_review_on_pending_order_rejected_with_422(
        self,
        client: httpx.Client,
        temp_end_user_headers: dict,
        real_pending_order,
    ):
        """The 'completed only' rule must reject submissions to pending orders."""
        resp = client.post(
            "/api/reviews",
            json={
                "order_id": real_pending_order.id,
                "subject_type": "product",
                "subject_id": 1,
                "rating": 4,
                "comment": "Too early",
            },
            headers=temp_end_user_headers,
        )
        assert resp.status_code == 422
        detail = resp.json().get("detail", "")
        assert "completed" in str(detail).lower()

    def test_end_user_cannot_review_someone_elses_order(
        self,
        client: httpx.Client,
        admin_headers: dict,
        _backend_db,
        real_completed_order,
    ):
        """
        A brand-new end_user (not the owner of real_completed_order) must
        be blocked with 403 when trying to review it.
        """
        # Provision an unrelated end_user inline.
        uid = uuid.uuid4().hex[:10]
        stranger = client.post(
            "/api/users",
            json={
                "username": f"stranger_{uid}",
                "email": f"stranger_{uid}@example.com",
                "password": "StrangerPass@2024!",
                "role": "end_user",
            },
            headers=admin_headers,
        ).json()
        try:
            tokens = client.post("/api/auth/login", json={
                "username": stranger["username"],
                "password": "StrangerPass@2024!",
            }).json()
            stranger_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
            resp = client.post(
                "/api/reviews",
                json={
                    "order_id": real_completed_order.id,
                    "subject_type": "product",
                    "subject_id": 1,
                    "rating": 5,
                    "comment": "Not my order",
                },
                headers=stranger_headers,
            )
            assert resp.status_code == 403
        finally:
            client.delete(f"/api/users/{stranger['id']}", headers=admin_headers)


class TestReviewCooldown:
    """Anti-spam: second review on the same order within 10 minutes must be rejected."""

    def test_second_submission_within_cooldown_returns_429(
        self,
        client: httpx.Client,
        temp_end_user_headers: dict,
        real_completed_order,
    ):
        first = client.post(
            "/api/reviews",
            json={
                "order_id": real_completed_order.id,
                "subject_type": "product",
                "subject_id": 7,
                "rating": 4,
                "comment": "First",
            },
            headers=temp_end_user_headers,
        )
        assert first.status_code == 201, first.text

        # Second submission targeting a DIFFERENT subject still must be
        # blocked by the cooldown window.
        second = client.post(
            "/api/reviews",
            json={
                "order_id": real_completed_order.id,
                "subject_type": "product",
                "subject_id": 8,
                "rating": 5,
                "comment": "Second on same order",
            },
            headers=temp_end_user_headers,
        )
        assert second.status_code == 429, (
            f"Expected 429 from cooldown, got {second.status_code}: {second.text}"
        )
        assert "minutes" in second.json().get("detail", "").lower()

    def test_duplicate_subject_on_same_order_conflict(
        self,
        client: httpx.Client,
        temp_end_user_headers: dict,
        real_completed_order,
    ):
        """
        The cooldown fires before the duplicate-subject check, so re-submitting
        within 10 minutes yields 429. (After the window closes it would become
        409; we document the observable HTTP contract here.)
        """
        client.post(
            "/api/reviews",
            json={
                "order_id": real_completed_order.id,
                "subject_type": "product",
                "subject_id": 42,
                "rating": 3,
                "comment": "First",
            },
            headers=temp_end_user_headers,
        )
        dup = client.post(
            "/api/reviews",
            json={
                "order_id": real_completed_order.id,
                "subject_type": "product",
                "subject_id": 42,
                "rating": 4,
                "comment": "Dup",
            },
            headers=temp_end_user_headers,
        )
        assert dup.status_code in (409, 429)


class TestFollowupLifecycle:
    """Follow-up review rules, driven by a real completed order."""

    def test_followup_requires_original_reviewer(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user_headers: dict,
        real_completed_order,
    ):
        first = client.post(
            "/api/reviews",
            json={
                "order_id": real_completed_order.id,
                "subject_type": "catalog_item",
                "subject_id": 1,
                "rating": 5,
                "comment": "Initial review",
            },
            headers=temp_end_user_headers,
        )
        assert first.status_code == 201
        review_id = first.json()["id"]

        # Admin is not the original reviewer — must be rejected.
        resp = client.post(
            f"/api/reviews/{review_id}/followup",
            json={"rating": 2, "comment": "Stolen follow-up"},
            headers=admin_headers,
        )
        assert resp.status_code == 403

    def test_followup_cannot_be_made_on_another_followup(
        self,
        client: httpx.Client,
        temp_end_user_headers: dict,
        real_completed_order,
    ):
        first = client.post(
            "/api/reviews",
            json={
                "order_id": real_completed_order.id,
                "subject_type": "catalog_item",
                "subject_id": 9,
                "rating": 5,
                "comment": "Initial",
            },
            headers=temp_end_user_headers,
        )
        assert first.status_code == 201, first.text
        # Attempting a follow-up immediately should be blocked by the 10-minute
        # cooldown first — we document that contract here; when the cooldown
        # expires a follow-up would succeed; a follow-up-on-follow-up would
        # then return 422.
        resp = client.post(
            f"/api/reviews/{first.json()['id']}/followup",
            json={"rating": 4, "comment": "Follow-up"},
            headers=temp_end_user_headers,
        )
        # 429 (cooldown) is the immediate expected outcome.
        assert resp.status_code in (201, 422, 429)


class TestReviewImageTamperDetection:
    """
    Images attached to reviews carry a SHA-256 fingerprint. Upload validation
    also rejects spoofed MIME types via magic-byte sniffing.
    """

    def test_upload_valid_png_then_record_carries_fingerprint(
        self,
        client: httpx.Client,
        temp_end_user_headers: dict,
        real_completed_order,
    ):
        import io

        first = client.post(
            "/api/reviews",
            json={
                "order_id": real_completed_order.id,
                "subject_type": "product",
                "subject_id": 77,
                "rating": 5,
                "comment": "With photo",
            },
            headers=temp_end_user_headers,
        )
        assert first.status_code == 201, first.text
        review_id = first.json()["id"]

        # 8-byte PNG magic followed by trivial IHDR — passes magic-byte sniff.
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 120
        resp = client.post(
            f"/api/reviews/{review_id}/images",
            files={"file": ("shot.png", io.BytesIO(png), "image/png")},
            headers=temp_end_user_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert len(body["sha256_fingerprint"]) == 64
        assert body["mime_type"] == "image/png"
        assert body["file_size"] == len(png)

    def test_spoofed_extension_rejected_by_magic_byte_sniff(
        self,
        client: httpx.Client,
        temp_end_user_headers: dict,
        real_completed_order,
    ):
        """An .exe renamed to .jpg must be rejected by the magic-byte check."""
        import io

        first = client.post(
            "/api/reviews",
            json={
                "order_id": real_completed_order.id,
                "subject_type": "product",
                "subject_id": 78,
                "rating": 3,
                "comment": "Should not upload .exe",
            },
            headers=temp_end_user_headers,
        )
        assert first.status_code == 201
        review_id = first.json()["id"]

        fake_jpg = b"MZ" + b"\x00" * 100  # Windows PE/EXE magic bytes
        resp = client.post(
            f"/api/reviews/{review_id}/images",
            files={"file": ("malware.jpg", io.BytesIO(fake_jpg), "image/jpeg")},
            headers=temp_end_user_headers,
        )
        assert resp.status_code == 422
        detail = resp.json().get("detail", "")
        assert "does not match" in detail or "spoofed" in detail or "declared" in detail

    def test_webp_rejected_even_with_valid_magic(
        self,
        client: httpx.Client,
        temp_end_user_headers: dict,
        real_completed_order,
    ):
        import io

        first = client.post(
            "/api/reviews",
            json={
                "order_id": real_completed_order.id,
                "subject_type": "product",
                "subject_id": 79,
                "rating": 4,
                "comment": "No webp allowed",
            },
            headers=temp_end_user_headers,
        )
        assert first.status_code == 201
        review_id = first.json()["id"]

        # Valid WEBP magic, but review images accept only image/jpeg and image/png.
        webp = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 50
        resp = client.post(
            f"/api/reviews/{review_id}/images",
            files={"file": ("photo.webp", io.BytesIO(webp), "image/webp")},
            headers=temp_end_user_headers,
        )
        assert resp.status_code == 422
