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
