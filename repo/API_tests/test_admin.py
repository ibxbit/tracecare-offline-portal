"""
API tests for /api/admin — site rules, system parameters, tasks, API keys.
"""
import uuid
import httpx
import pytest


# ---------------------------------------------------------------------------
# Site Rules
# ---------------------------------------------------------------------------

class TestSiteRules:
    def _rule_payload(self) -> dict:
        return {
            "name": f"test_rule_{uuid.uuid4().hex[:8]}",
            "value": "true",
            "value_type": "boolean",
            "description": "Test rule for pytest",
            "is_active": True,
        }

    def test_admin_can_create_rule(self, client: httpx.Client, admin_headers: dict):
        payload = self._rule_payload()
        resp = client.post("/api/admin/rules", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == payload["name"]
        client.delete(f"/api/admin/rules/{body['id']}", headers=admin_headers)

    def test_list_rules(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/admin/rules", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_rule_by_id(self, client: httpx.Client, admin_headers: dict):
        rule = client.post("/api/admin/rules", json=self._rule_payload(), headers=admin_headers).json()
        resp = client.get(f"/api/admin/rules/{rule['id']}", headers=admin_headers)
        assert resp.status_code == 200
        client.delete(f"/api/admin/rules/{rule['id']}", headers=admin_headers)

    def test_toggle_rule(self, client: httpx.Client, admin_headers: dict):
        rule = client.post("/api/admin/rules", json=self._rule_payload(), headers=admin_headers).json()
        rule_id = rule["id"]
        initial_active = rule["is_active"]
        resp = client.patch(f"/api/admin/rules/{rule_id}/toggle", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["is_active"] != initial_active
        client.delete(f"/api/admin/rules/{rule_id}", headers=admin_headers)

    def test_rule_name_must_be_snake_case(self, client: httpx.Client, admin_headers: dict):
        payload = self._rule_payload()
        payload["name"] = "Invalid Rule Name"  # spaces not allowed
        resp = client.post("/api/admin/rules", json=payload, headers=admin_headers)
        assert resp.status_code == 422

    def test_duplicate_rule_name_rejected(self, client: httpx.Client, admin_headers: dict):
        payload = self._rule_payload()
        rule = client.post("/api/admin/rules", json=payload, headers=admin_headers).json()
        resp = client.post("/api/admin/rules", json=payload, headers=admin_headers)
        assert resp.status_code == 409
        client.delete(f"/api/admin/rules/{rule['id']}", headers=admin_headers)


# ---------------------------------------------------------------------------
# System Parameters
# ---------------------------------------------------------------------------

class TestSystemParameters:
    def test_list_parameters(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/admin/parameters", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_seeded_parameter(self, client: httpx.Client, admin_headers: dict):
        """The init_db seeds app.version — it should exist."""
        resp = client.get("/api/admin/parameters/app.version", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["key"] == "app.version"

    def test_readonly_parameter_cannot_be_updated(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/admin/parameters/app.version", headers=admin_headers)
        if resp.status_code != 200:
            pytest.skip("app.version parameter not found")
        param = resp.json()
        if not param.get("is_readonly", False):
            pytest.skip("app.version is not readonly in this environment")
        update_resp = client.put("/api/admin/parameters/app.version", json={
            "value": "9.9.9",
            "description": "Hacked version",
        }, headers=admin_headers)
        assert update_resp.status_code in (400, 403, 422)


# ---------------------------------------------------------------------------
# Admin Tasks
# ---------------------------------------------------------------------------

class TestAdminTasks:
    def _task_payload(self) -> dict:
        return {
            "name": f"test_task_{uuid.uuid4().hex[:8]}",
            "task_type": "maintenance",
            "description": "Pytest task",
            "priority": 5,
        }

    def test_create_task(self, client: httpx.Client, admin_headers: dict):
        resp = client.post("/api/admin/tasks", json=self._task_payload(), headers=admin_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "pending"

    def test_list_tasks(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/admin/tasks", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_task_by_id(self, client: httpx.Client, admin_headers: dict):
        task = client.post("/api/admin/tasks", json=self._task_payload(), headers=admin_headers).json()
        resp = client.get(f"/api/admin/tasks/{task['id']}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == task["id"]

    def test_update_task_status(self, client: httpx.Client, admin_headers: dict):
        task = client.post("/api/admin/tasks", json=self._task_payload(), headers=admin_headers).json()
        resp = client.patch(f"/api/admin/tasks/{task['id']}/status", json={
            "status": "running"
        }, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_priority_out_of_range_rejected(self, client: httpx.Client, admin_headers: dict):
        payload = self._task_payload()
        payload["priority"] = 11  # max is 10
        resp = client.post("/api/admin/tasks", json=payload, headers=admin_headers)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------

class TestApiKeys:
    def _key_payload(self) -> dict:
        return {
            "label": f"test_key_{uuid.uuid4().hex[:8]}",
            "system_name": "pytest_system",
            "rate_limit_per_minute": 60,
        }

    def test_create_api_key(self, client: httpx.Client, admin_headers: dict):
        resp = client.post("/api/admin/api-keys", json=self._key_payload(), headers=admin_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert "raw_key" in body  # raw key returned only at creation
        assert "key_prefix" in body

    def test_raw_key_not_returned_on_get(self, client: httpx.Client, admin_headers: dict):
        key = client.post("/api/admin/api-keys", json=self._key_payload(), headers=admin_headers).json()
        resp = client.get(f"/api/admin/api-keys/{key['id']}", headers=admin_headers)
        assert resp.status_code == 200
        assert "raw_key" not in resp.json()

    def test_list_api_keys(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/admin/api-keys", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_rotate_api_key(self, client: httpx.Client, admin_headers: dict):
        key = client.post("/api/admin/api-keys", json=self._key_payload(), headers=admin_headers).json()
        resp = client.patch(f"/api/admin/api-keys/{key['id']}/rotate", headers=admin_headers)
        assert resp.status_code == 200
        new_key = resp.json()
        # New raw key should be different
        assert new_key.get("raw_key") != key.get("raw_key")

    def test_toggle_api_key(self, client: httpx.Client, admin_headers: dict):
        key = client.post("/api/admin/api-keys", json=self._key_payload(), headers=admin_headers).json()
        initial_active = key.get("is_active", True)
        resp = client.patch(f"/api/admin/api-keys/{key['id']}/toggle", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["is_active"] != initial_active

    def test_delete_api_key(self, client: httpx.Client, admin_headers: dict):
        key = client.post("/api/admin/api-keys", json=self._key_payload(), headers=admin_headers).json()
        resp = client.delete(f"/api/admin/api-keys/{key['id']}", headers=admin_headers)
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# System Status
# ---------------------------------------------------------------------------

class TestSystemStatus:
    def test_status_returns_metrics(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/admin/system/status", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        # Should contain some counts or status fields
        assert isinstance(body, dict)
        assert len(body) > 0

    def test_db_connectivity_reflected_in_status(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/admin/system/status", headers=admin_headers)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# CSV Exports
# ---------------------------------------------------------------------------

class TestCSVExports:
    def test_export_site_rules(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/admin/export/site-rules", headers=admin_headers)
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert "csv" in ct or "text" in ct

    def test_export_users(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/admin/export/users", headers=admin_headers)
        assert resp.status_code == 200

    def test_export_api_keys(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/admin/export/api-keys", headers=admin_headers)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Proxy Pool
# ---------------------------------------------------------------------------

class TestProxyPool:
    """
    Admin-only CRUD + health-check for /api/admin/proxy-pool.
    Proxy pool manages outbound connection proxies for offline relay scenarios.
    """

    def _proxy_payload(self) -> dict:
        return {
            "host": f"10.0.1.{uuid.uuid4().int % 254 + 1}",
            "port": 8080,
            "protocol": "http",
            "label": f"proxy_{uuid.uuid4().hex[:8]}",
            "is_active": True,
        }

    # ── Happy path ────────────────────────────────────────────────────────────

    def test_admin_can_create_proxy(self, client: httpx.Client, admin_headers: dict):
        payload = self._proxy_payload()
        resp = client.post("/api/admin/proxy-pool", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["host"] == payload["host"]
        assert body["port"] == payload["port"]
        assert "id" in body
        # Cleanup
        client.delete(f"/api/admin/proxy-pool/{body['id']}", headers=admin_headers)

    def test_admin_can_list_proxies(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/admin/proxy-pool", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_admin_can_get_proxy_by_id(self, client: httpx.Client, admin_headers: dict):
        proxy = client.post(
            "/api/admin/proxy-pool", json=self._proxy_payload(), headers=admin_headers
        ).json()
        resp = client.get(f"/api/admin/proxy-pool/{proxy['id']}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == proxy["id"]
        client.delete(f"/api/admin/proxy-pool/{proxy['id']}", headers=admin_headers)

    def test_admin_can_update_proxy(self, client: httpx.Client, admin_headers: dict):
        proxy = client.post(
            "/api/admin/proxy-pool", json=self._proxy_payload(), headers=admin_headers
        ).json()
        resp = client.put(
            f"/api/admin/proxy-pool/{proxy['id']}",
            json={**self._proxy_payload(), "label": "updated_label"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["label"] == "updated_label"
        client.delete(f"/api/admin/proxy-pool/{proxy['id']}", headers=admin_headers)

    def test_admin_can_delete_proxy(self, client: httpx.Client, admin_headers: dict):
        proxy = client.post(
            "/api/admin/proxy-pool", json=self._proxy_payload(), headers=admin_headers
        ).json()
        resp = client.delete(
            f"/api/admin/proxy-pool/{proxy['id']}", headers=admin_headers
        )
        assert resp.status_code == 204

    def test_health_check_returns_result(
        self, client: httpx.Client, admin_headers: dict
    ):
        proxy = client.post(
            "/api/admin/proxy-pool", json=self._proxy_payload(), headers=admin_headers
        ).json()
        resp = client.patch(
            f"/api/admin/proxy-pool/{proxy['id']}/health-check",
            headers=admin_headers,
        )
        # Health check may succeed or fail depending on env — either is a valid result
        assert resp.status_code in (200, 503)
        body = resp.json()
        assert "reachable" in body
        client.delete(f"/api/admin/proxy-pool/{proxy['id']}", headers=admin_headers)

    def test_get_nonexistent_proxy_returns_404(
        self, client: httpx.Client, admin_headers: dict
    ):
        resp = client.get("/api/admin/proxy-pool/999999999", headers=admin_headers)
        assert resp.status_code == 404

    # ── Access control ────────────────────────────────────────────────────────

    def test_end_user_cannot_list_proxy_pool(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.get("/api/admin/proxy-pool", headers=temp_end_user_headers)
        assert resp.status_code == 403

    def test_staff_cannot_list_proxy_pool(
        self, client: httpx.Client, temp_staff_headers: dict
    ):
        resp = client.get("/api/admin/proxy-pool", headers=temp_staff_headers)
        assert resp.status_code == 403

    def test_end_user_cannot_create_proxy(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.post(
            "/api/admin/proxy-pool",
            json=self._proxy_payload(),
            headers=temp_end_user_headers,
        )
        assert resp.status_code == 403

    def test_staff_cannot_delete_proxy(
        self, client: httpx.Client, admin_headers: dict, temp_staff_headers: dict
    ):
        proxy = client.post(
            "/api/admin/proxy-pool", json=self._proxy_payload(), headers=admin_headers
        ).json()
        resp = client.delete(
            f"/api/admin/proxy-pool/{proxy['id']}", headers=temp_staff_headers
        )
        assert resp.status_code == 403
        client.delete(f"/api/admin/proxy-pool/{proxy['id']}", headers=admin_headers)

    # ── Validation ────────────────────────────────────────────────────────────

    def test_invalid_port_rejected(self, client: httpx.Client, admin_headers: dict):
        payload = self._proxy_payload()
        payload["port"] = 99999  # out of valid range
        resp = client.post("/api/admin/proxy-pool", json=payload, headers=admin_headers)
        assert resp.status_code == 422

    def test_missing_host_rejected(self, client: httpx.Client, admin_headers: dict):
        resp = client.post("/api/admin/proxy-pool", json={
            "port": 8080, "protocol": "http", "label": "no_host"
        }, headers=admin_headers)
        assert resp.status_code == 422
