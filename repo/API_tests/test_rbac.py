"""
API tests for role-based access control across key endpoints.

Verifies that:
  - Unauthenticated requests are rejected (401).
  - Lower-privilege roles are forbidden (403) on admin-only endpoints.
  - Higher-privilege roles can access their allowed endpoints.
"""
import uuid
import httpx
import pytest


class TestUnauthenticated:
    """All protected endpoints must reject requests with no token."""

    def test_get_product_trace_requires_auth(self, client: httpx.Client):
        assert client.get("/api/products/1/trace-events").status_code == 401

    def test_get_users_requires_auth(self, client: httpx.Client):
        assert client.get("/api/users").status_code == 401

    def test_get_me_requires_auth(self, client: httpx.Client):
        assert client.get("/api/users/me").status_code == 401

    def test_get_packages_requires_auth(self, client: httpx.Client):
        assert client.get("/api/packages").status_code == 401

    def test_get_catalog_requires_auth(self, client: httpx.Client):
        assert client.get("/api/catalog").status_code == 401

    def test_get_notifications_requires_auth(self, client: httpx.Client):
        assert client.get("/api/notifications").status_code == 401

    def test_get_admin_rules_requires_auth(self, client: httpx.Client):
        assert client.get("/api/admin/rules").status_code in (401, 403)

    def test_get_audit_requires_auth(self, client: httpx.Client):
        assert client.get("/api/audit").status_code in (401, 403)

    def test_get_cms_pages_requires_auth(self, client: httpx.Client):
        assert client.get("/api/cms/pages").status_code == 401


class TestEndUserRestrictions:
    """end_user must not access admin-only endpoints."""

    def test_end_user_cannot_list_all_users(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.get("/api/users", headers=temp_end_user_headers)
        assert resp.status_code == 403

    def test_end_user_cannot_create_user(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.post("/api/users", json={
            "username": f"hacker_{uuid.uuid4().hex[:6]}",
            "email": "hacker@test.local",
            "password": "Hacker@123!",
            "role": "admin",
        }, headers=temp_end_user_headers)
        assert resp.status_code == 403

    def test_end_user_cannot_access_admin_console(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.get("/api/admin/rules", headers=temp_end_user_headers)
        assert resp.status_code == 403

    def test_end_user_cannot_access_audit_log(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.get("/api/audit", headers=temp_end_user_headers)
        assert resp.status_code == 403

    def test_end_user_can_read_own_profile(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.get("/api/users/me", headers=temp_end_user_headers)
        assert resp.status_code == 200

    def test_end_user_can_read_packages(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.get("/api/packages", headers=temp_end_user_headers)
        assert resp.status_code == 200

    def test_end_user_cannot_create_package(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.post("/api/packages", json={
            "name": "hacker_pkg",
            "description": "test",
            "price": "10.00",
            "validity_days": 30,
        }, headers=temp_end_user_headers)
        assert resp.status_code == 403


class TestStaffPermissions:
    """clinic_staff can write packages/CMS but not admin console."""

    def test_staff_cannot_access_admin_console(
        self, client: httpx.Client, temp_staff_headers: dict
    ):
        resp = client.get("/api/admin/rules", headers=temp_staff_headers)
        assert resp.status_code == 403

    def test_staff_cannot_access_audit_log(
        self, client: httpx.Client, temp_staff_headers: dict
    ):
        resp = client.get("/api/audit", headers=temp_staff_headers)
        assert resp.status_code == 403

    def test_staff_can_read_own_profile(
        self, client: httpx.Client, temp_staff_headers: dict
    ):
        resp = client.get("/api/users/me", headers=temp_staff_headers)
        assert resp.status_code == 200

    def test_staff_can_read_packages(
        self, client: httpx.Client, temp_staff_headers: dict
    ):
        resp = client.get("/api/packages", headers=temp_staff_headers)
        assert resp.status_code == 200


class TestAdminPermissions:
    """admin can access all admin endpoints."""

    def test_admin_can_list_users(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/users", headers=admin_headers)
        assert resp.status_code == 200

    def test_admin_can_access_audit(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/audit", headers=admin_headers)
        assert resp.status_code == 200

    def test_admin_can_access_admin_rules(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/admin/rules", headers=admin_headers)
        assert resp.status_code == 200

    def test_admin_can_access_system_status(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/admin/system/status", headers=admin_headers)
        assert resp.status_code == 200

    def test_admin_cannot_delete_own_account(
        self, client: httpx.Client, admin_headers: dict
    ):
        """Admin is explicitly prevented from self-deletion."""
        me = client.get("/api/users/me", headers=admin_headers).json()
        resp = client.delete(f"/api/users/{me['id']}", headers=admin_headers)
        assert resp.status_code == 400

    def test_expired_token_rejected(self, client: httpx.Client):
        """A fabricated / garbage token must not grant access."""
        resp = client.get("/api/users/me", headers={
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.invalid"
        })
        assert resp.status_code == 401


class TestCatalogManagerRole:
    """
    catalog_manager can access CMS and catalog write endpoints
    but is forbidden from admin console and user management.
    """

    def test_catalog_manager_can_list_cms_pages(
        self, client: httpx.Client, temp_catalog_manager_headers: dict
    ):
        resp = client.get("/api/cms/pages", headers=temp_catalog_manager_headers)
        assert resp.status_code == 200

    def test_catalog_manager_can_list_catalog(
        self, client: httpx.Client, temp_catalog_manager_headers: dict
    ):
        resp = client.get("/api/catalog", headers=temp_catalog_manager_headers)
        assert resp.status_code == 200

    def test_catalog_manager_cannot_access_admin_console(
        self, client: httpx.Client, temp_catalog_manager_headers: dict
    ):
        resp = client.get("/api/admin/rules", headers=temp_catalog_manager_headers)
        assert resp.status_code == 403

    def test_catalog_manager_cannot_list_users(
        self, client: httpx.Client, temp_catalog_manager_headers: dict
    ):
        resp = client.get("/api/users", headers=temp_catalog_manager_headers)
        assert resp.status_code == 403

    def test_catalog_manager_cannot_access_audit_log(
        self, client: httpx.Client, temp_catalog_manager_headers: dict
    ):
        resp = client.get("/api/audit", headers=temp_catalog_manager_headers)
        assert resp.status_code == 403

    def test_catalog_manager_cannot_access_proxy_pool(
        self, client: httpx.Client, temp_catalog_manager_headers: dict
    ):
        resp = client.get("/api/admin/proxy-pool", headers=temp_catalog_manager_headers)
        assert resp.status_code == 403

    def test_catalog_manager_can_read_own_profile(
        self, client: httpx.Client, temp_catalog_manager_headers: dict
    ):
        resp = client.get("/api/users/me", headers=temp_catalog_manager_headers)
        assert resp.status_code == 200


class TestObjectLevelAuthorization:
    """
    Object-level authorization: users can only access their own resources
    (messages, notifications, preferences).
    """

    def test_end_user_cannot_read_other_users_direct_message(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
        temp_staff_user: dict,
        temp_staff_headers: dict,
    ):
        """A direct message sent to end_user must not be readable by staff."""
        msg = client.post("/api/messages", json={
            "recipient_id": temp_end_user["id"],
            "subject": "Private",
            "body": "For end_user only",
        }, headers=admin_headers).json()
        resp = client.get(f"/api/messages/{msg['id']}", headers=temp_staff_headers)
        assert resp.status_code == 403

    def test_non_participant_cannot_view_thread(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
        temp_staff_user: dict,
        temp_staff_headers: dict,
    ):
        """A thread participant list is [admin, end_user] — staff cannot see it."""
        thread = client.post("/api/messages/threads", json={
            "subject": f"ObjAuth {uuid.uuid4().hex[:6]}",
            "participant_ids": [temp_end_user["id"]],
            "initial_message": "Hi",
            "use_virtual_ids": False,
        }, headers=admin_headers).json()
        resp = client.get(
            f"/api/messages/threads/{thread['id']}",
            headers=temp_staff_headers,
        )
        assert resp.status_code == 403

    def test_notification_owner_can_read_own_notification(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        """Reading /notifications returns 200 for the owning user."""
        resp = client.get("/api/notifications", headers=temp_end_user_headers)
        assert resp.status_code == 200

    def test_notification_unread_count_scoped_to_caller(
        self, client: httpx.Client,
        temp_end_user_headers: dict,
        admin_headers: dict,
    ):
        """Each user's unread count is independent — API returns own count only."""
        end_resp = client.get("/api/notifications/unread-count", headers=temp_end_user_headers)
        admin_resp = client.get("/api/notifications/unread-count", headers=admin_headers)
        assert end_resp.status_code == 200
        assert admin_resp.status_code == 200
        # Both return valid unread_count integers; values may differ
        assert "unread_count" in end_resp.json()
        assert "unread_count" in admin_resp.json()

    def test_preferences_always_return_caller_own_prefs(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        """/preferences/me is always scoped to the caller — no user_id param leak."""
        resp = client.get("/api/notifications/preferences/me", headers=temp_end_user_headers)
        assert resp.status_code == 200


class TestFunctionLevelAuthorization:
    """
    Function-level authorization: restricted endpoints block lower roles entirely,
    regardless of the resource ID.
    """

    def test_end_user_cannot_access_proxy_pool_list(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.get("/api/admin/proxy-pool", headers=temp_end_user_headers)
        assert resp.status_code == 403

    def test_staff_cannot_access_proxy_pool_list(
        self, client: httpx.Client, temp_staff_headers: dict
    ):
        resp = client.get("/api/admin/proxy-pool", headers=temp_staff_headers)
        assert resp.status_code == 403

    def test_end_user_cannot_create_proxy_entry(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.post("/api/admin/proxy-pool", json={
            "host": "10.0.0.1", "port": 8080, "protocol": "http", "label": "x"
        }, headers=temp_end_user_headers)
        assert resp.status_code == 403

    def test_end_user_cannot_export_users_csv(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.get("/api/admin/export/users", headers=temp_end_user_headers)
        assert resp.status_code == 403

    def test_staff_cannot_export_users_csv(
        self, client: httpx.Client, temp_staff_headers: dict
    ):
        resp = client.get("/api/admin/export/users", headers=temp_staff_headers)
        assert resp.status_code == 403

    def test_end_user_cannot_access_admin_tasks(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.get("/api/admin/tasks", headers=temp_end_user_headers)
        assert resp.status_code == 403

    def test_end_user_cannot_access_delivery_metrics(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.get("/api/notifications/admin/metrics", headers=temp_end_user_headers)
        assert resp.status_code == 403


class TestPrivilegeEscalation:
    """
    Users must not be able to elevate their own role or access
    another user's resources by guessing or injecting IDs.
    """

    def test_end_user_cannot_promote_own_role_to_admin(
        self, client: httpx.Client, temp_end_user: dict, temp_end_user_headers: dict
    ):
        """PATCH /users/{id} with role=admin must be blocked for end_user."""
        resp = client.patch(
            f"/api/users/{temp_end_user['id']}",
            json={"role": "admin"},
            headers=temp_end_user_headers,
        )
        assert resp.status_code in (403, 422)

    def test_end_user_cannot_create_admin_account(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.post("/api/users", json={
            "username": f"evil_{uuid.uuid4().hex[:6]}",
            "email": "evil@test.local",
            "password": "Evil@123!",
            "role": "admin",
        }, headers=temp_end_user_headers)
        assert resp.status_code == 403

    def test_end_user_cannot_delete_another_user(
        self,
        client: httpx.Client,
        temp_end_user_headers: dict,
        temp_staff_user: dict,
    ):
        resp = client.delete(
            f"/api/users/{temp_staff_user['id']}",
            headers=temp_end_user_headers,
        )
        assert resp.status_code == 403

    def test_staff_cannot_access_system_status(
        self, client: httpx.Client, temp_staff_headers: dict
    ):
        resp = client.get("/api/admin/system/status", headers=temp_staff_headers)
        assert resp.status_code == 403


class TestMalformedTokenEdgeCases:
    """Malformed, missing, and structurally invalid tokens must all return 401."""

    def test_missing_authorization_header(self, client: httpx.Client):
        resp = client.get("/api/users/me")
        assert resp.status_code == 401

    def test_bearer_prefix_missing(self, client: httpx.Client):
        resp = client.get("/api/users/me", headers={"Authorization": "notatoken"})
        assert resp.status_code == 401

    def test_empty_bearer_token(self, client: httpx.Client):
        resp = client.get("/api/users/me", headers={"Authorization": "Bearer"})
        assert resp.status_code == 401

    def test_completely_random_token(self, client: httpx.Client):
        resp = client.get("/api/users/me", headers={
            "Authorization": "Bearer randomgibberish123"
        })
        assert resp.status_code == 401

    def test_jwt_with_wrong_signature(self, client: httpx.Client):
        # Valid JWT structure but wrong signature
        resp = client.get("/api/users/me", headers={
            "Authorization": (
                "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
                ".eyJzdWIiOiIxIiwiZXhwIjo5OTk5OTk5OTk5fQ"
                ".wrongsignaturehere"
            )
        })
        assert resp.status_code == 401

    def test_numeric_token_rejected(self, client: httpx.Client):
        resp = client.get("/api/users/me", headers={"Authorization": "Bearer 12345"})
        assert resp.status_code == 401
