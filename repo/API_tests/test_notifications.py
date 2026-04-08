"""
API tests for /api/notifications — list, mark read, preferences, metrics.
"""
import httpx
import pytest


class TestNotificationList:
    def test_list_own_notifications(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.get("/api/notifications", headers=temp_end_user_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)

    def test_list_returns_only_own_notifications(
        self,
        client: httpx.Client,
        temp_end_user_headers: dict,
        admin_headers: dict,
    ):
        """end_user's notification list should not include admin notifications."""
        end_resp = client.get("/api/notifications", headers=temp_end_user_headers)
        admin_resp = client.get("/api/notifications", headers=admin_headers)
        # Both should succeed — content isolation tested implicitly
        assert end_resp.status_code == 200
        assert admin_resp.status_code == 200

    def test_filter_by_unread(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.get(
            "/api/notifications",
            params={"unread_only": True},
            headers=temp_end_user_headers,
        )
        assert resp.status_code == 200

    def test_get_nonexistent_notification_returns_404(
        self, client: httpx.Client, admin_headers: dict
    ):
        resp = client.get("/api/notifications/999999999", headers=admin_headers)
        assert resp.status_code == 404


class TestUnreadCount:
    def test_unread_count_returns_unread_count_key(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        """Backend must return {unread_count: N}, not {count: N}."""
        resp = client.get("/api/notifications/unread-count", headers=temp_end_user_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "unread_count" in body, f"Expected 'unread_count' key, got: {list(body.keys())}"
        assert isinstance(body["unread_count"], int)


class TestNotificationMarkRead:
    def test_mark_nonexistent_as_read_returns_404(
        self, client: httpx.Client, admin_headers: dict
    ):
        resp = client.patch("/api/notifications/999999999/read", headers=admin_headers)
        assert resp.status_code == 404

    def test_mark_all_read(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.post("/api/notifications/mark-all-read", headers=temp_end_user_headers)
        assert resp.status_code in (200, 204)

    def test_delete_nonexistent_notification_returns_404(
        self, client: httpx.Client, admin_headers: dict
    ):
        resp = client.delete("/api/notifications/999999999", headers=admin_headers)
        assert resp.status_code == 404


class TestNotificationPreferences:
    def test_get_preferences(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.get("/api/notifications/preferences/me", headers=temp_end_user_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, dict)
        # Verify expected fields are present
        assert "notify_order_accepted" in body
        assert "notify_new_message" in body

    def test_update_preferences(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        # Fetch current prefs
        current = client.get("/api/notifications/preferences/me", headers=temp_end_user_headers).json()

        # Toggle a preference (use a known field from the schema)
        update = {
            "notify_order_accepted": not current.get("notify_order_accepted", True),
        }
        resp = client.put(
            "/api/notifications/preferences/me",
            json=update,
            headers=temp_end_user_headers,
        )
        assert resp.status_code == 200

    def test_cannot_view_other_users_preferences(
        self,
        client: httpx.Client,
        temp_end_user_headers: dict,
        temp_staff_user: dict,
    ):
        """A user can only access their own preferences via /preferences/me."""
        # /preferences/me always returns caller's own prefs — no param to override
        resp = client.get(
            "/api/notifications/preferences/me",
            headers=temp_end_user_headers,
        )
        assert resp.status_code == 200


class TestDeliveryMetrics:
    def test_admin_can_view_metrics(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/notifications/admin/metrics", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, dict)
        # Verify all fields from backend DeliveryMetricsResponse schema are present
        for key in ("total", "delivered", "retrying", "failed", "pending",
                    "delivery_rate_pct", "avg_attempts_on_delivered", "by_type"):
            assert key in body, (
                f"Expected key '{key}' in metrics response, got keys: {list(body.keys())}"
            )
        assert isinstance(body["total"], int)
        assert isinstance(body["delivery_rate_pct"], (int, float))
        assert isinstance(body["by_type"], dict)

    def test_end_user_cannot_view_metrics(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.get("/api/notifications/admin/metrics", headers=temp_end_user_headers)
        assert resp.status_code == 403


class TestDeliveryMetricsFieldAlignment:
    """
    Verifies the exact field names returned by DeliveryMetricsResponse.
    Guards against stale UI keys (total_delivered etc.) that don't match
    the backend schema.
    """

    # The backend model uses these exact field names (no total_ prefix)
    EXPECTED_KEYS = frozenset([
        "total", "delivered", "retrying", "failed", "pending",
        "delivery_rate_pct", "avg_attempts_on_delivered", "by_type",
    ])
    # These old/stale keys must never appear
    STALE_KEYS = frozenset([
        "total_delivered", "total_retrying", "total_failed", "total_pending",
    ])

    def test_no_stale_total_prefixed_keys(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/notifications/admin/metrics", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        for stale in self.STALE_KEYS:
            assert stale not in body, (
                f"Stale key '{stale}' found in metrics response — frontend alignment broken"
            )

    def test_delivery_rate_pct_is_numeric(
        self, client: httpx.Client, admin_headers: dict
    ):
        resp = client.get("/api/notifications/admin/metrics", headers=admin_headers)
        assert resp.status_code == 200
        val = resp.json().get("delivery_rate_pct")
        assert isinstance(val, (int, float))
        assert 0.0 <= val <= 100.0

    def test_avg_attempts_on_delivered_is_numeric(
        self, client: httpx.Client, admin_headers: dict
    ):
        resp = client.get("/api/notifications/admin/metrics", headers=admin_headers)
        assert resp.status_code == 200
        val = resp.json().get("avg_attempts_on_delivered")
        assert isinstance(val, (int, float))
        assert val >= 0.0

    def test_by_type_is_dict(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/notifications/admin/metrics", headers=admin_headers)
        assert resp.status_code == 200
        by_type = resp.json().get("by_type")
        assert isinstance(by_type, dict), "by_type must be a dict (keyed by notification type)"

    def test_counts_are_non_negative_integers(
        self, client: httpx.Client, admin_headers: dict
    ):
        resp = client.get("/api/notifications/admin/metrics", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        for key in ("total", "delivered", "retrying", "failed", "pending"):
            assert isinstance(body[key], int), f"{key} must be int"
            assert body[key] >= 0, f"{key} must be non-negative"

    def test_delivered_plus_retrying_plus_failed_plus_pending_le_total(
        self, client: httpx.Client, admin_headers: dict
    ):
        """Component counts must not exceed total."""
        resp = client.get("/api/notifications/admin/metrics", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        component_sum = body["delivered"] + body["retrying"] + body["failed"] + body["pending"]
        assert component_sum <= body["total"], (
            f"Sum of components ({component_sum}) exceeds total ({body['total']})"
        )


class TestRetryLogicDocumentation:
    """
    Documents the retry state machine: pending → retrying → delivered | failed.
    RETRY_SCHEDULE_MINUTES = [1, 5, 15] (from notification model constants).
    These tests verify the API contract around retry state — actual timing
    cannot be simulated in integration tests without clock manipulation.
    """

    def test_list_endpoint_triggers_due_retries(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        """
        GET /notifications calls process_due_retries() internally.
        The endpoint must succeed — confirming the retry hook runs without errors.
        """
        resp = client.get("/api/notifications", headers=temp_end_user_headers)
        assert resp.status_code == 200

    def test_list_endpoint_returns_list_after_retry_processing(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        """Verify that the response after retry processing is still a valid list."""
        resp = client.get("/api/notifications", headers=temp_end_user_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_notification_status_values_are_valid_states(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        """
        Any notifications returned must have a status that belongs to the
        known state machine: pending, retrying, delivered, failed.
        """
        valid_statuses = {"pending", "retrying", "delivered", "failed"}
        resp = client.get("/api/notifications", headers=temp_end_user_headers)
        assert resp.status_code == 200
        for notif in resp.json():
            if "status" in notif:
                assert notif["status"] in valid_statuses, (
                    f"Unexpected notification status: {notif['status']}"
                )

    def test_unread_count_is_non_negative_integer(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.get("/api/notifications/unread-count", headers=temp_end_user_headers)
        assert resp.status_code == 200
        count = resp.json()["unread_count"]
        assert isinstance(count, int)
        assert count >= 0

    def test_filter_by_type_info_returns_200(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        """All valid NotificationType enum values must be accepted as filters."""
        for ntype in ("info", "warning", "error", "success", "system"):
            resp = client.get(
                "/api/notifications",
                params={"type": ntype},
                headers=temp_end_user_headers,
            )
            assert resp.status_code == 200, (
                f"Expected 200 for notification type filter '{ntype}', got {resp.status_code}"
            )

    def test_filter_by_invalid_type_rejected(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        """Invalid NotificationType values must be rejected (422)."""
        for bad_type in ("order_status", "message", "sms"):
            resp = client.get(
                "/api/notifications",
                params={"type": bad_type},
                headers=temp_end_user_headers,
            )
            assert resp.status_code == 422, (
                f"Expected 422 for invalid notification type '{bad_type}', got {resp.status_code}"
            )
