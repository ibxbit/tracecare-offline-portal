"""
API tests for /api/audit — read-only audit log endpoints (admin only).
"""
import httpx
import pytest


class TestAuditList:
    def test_admin_can_list_audit_logs(self, client: httpx.Client, admin_headers: dict):
        r = client.get("/api/audit", headers=admin_headers)
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list)
        if body:
            assert "event_type" in body[0]
            assert "created_at" in body[0]

    def test_end_user_cannot_list_audit(self, client: httpx.Client, temp_end_user_headers: dict):
        r = client.get("/api/audit", headers=temp_end_user_headers)
        assert r.status_code == 403

    def test_filter_by_event_type(self, client: httpx.Client, admin_headers: dict):
        r = client.get("/api/audit", params={"event_type": "login_success"}, headers=admin_headers)
        assert r.status_code == 200
        for entry in r.json():
            assert entry["event_type"] == "login_success"

    def test_filter_by_user_id(self, client: httpx.Client, admin_headers: dict):
        r = client.get("/api/audit", params={"user_id": 1}, headers=admin_headers)
        assert r.status_code == 200

    def test_pagination(self, client: httpx.Client, admin_headers: dict):
        r = client.get("/api/audit", params={"skip": 0, "limit": 5}, headers=admin_headers)
        assert r.status_code == 200
        assert len(r.json()) <= 5


class TestAuditGetById:
    def test_get_specific_log_entry(self, client: httpx.Client, admin_headers: dict):
        logs = client.get("/api/audit", params={"limit": 1}, headers=admin_headers).json()
        if not logs:
            pytest.skip("No audit log entries yet")
        log_id = logs[0]["id"]
        r = client.get(f"/api/audit/{log_id}", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["id"] == log_id

    def test_get_nonexistent_log_returns_404(self, client: httpx.Client, admin_headers: dict):
        r = client.get("/api/audit/999999999", headers=admin_headers)
        assert r.status_code == 404

    def test_end_user_cannot_get_log(self, client: httpx.Client, temp_end_user_headers: dict):
        r = client.get("/api/audit/1", headers=temp_end_user_headers)
        assert r.status_code == 403
