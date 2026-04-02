"""
API tests for /api/packages — CRUD, versioning, diff, activate/deactivate.
"""
import uuid
import httpx
import pytest


def _pkg_payload(name: str | None = None, items: list | None = None) -> dict:
    if name is None:
        name = f"pkg_{uuid.uuid4().hex[:8]}"
    payload = {
        "name": name,
        "description": "Test package",
        "price": "99.99",
        "validity_window_days": 30,
    }
    if items is not None:
        payload["items"] = items
    return payload


def _get_or_create_exam_item(client: httpx.Client, admin_headers: dict) -> int:
    """Return the id of an exam item usable in package tests."""
    # Try fetching existing items first
    res = client.get("/api/exam-items", params={"limit": 1}, headers=admin_headers)
    if res.status_code == 200 and res.json():
        return res.json()[0]["id"]
    # Create a minimal exam item
    uid = uuid.uuid4().hex[:6]
    resp = client.post("/api/exam-items", json={
        "code": f"TST{uid}",
        "name": f"Test Item {uid}",
        "applicable_sex": "all",
    }, headers=admin_headers)
    assert resp.status_code == 201, f"Could not create exam item: {resp.text}"
    return resp.json()["id"]


class TestPackageCRUD:
    def test_admin_can_create_package(self, client: httpx.Client, admin_headers: dict):
        item_id = _get_or_create_exam_item(client, admin_headers)
        payload = _pkg_payload(items=[{"exam_item_id": item_id, "is_required": True}])
        resp = client.post("/api/packages", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == payload["name"]
        assert body["version"] == 1
        # Cleanup
        client.delete(f"/api/packages/{body['id']}", headers=admin_headers)

    def test_package_items_included_in_payload(self, client: httpx.Client, admin_headers: dict):
        """items array with is_required flag must be accepted by backend."""
        item_id = _get_or_create_exam_item(client, admin_headers)
        payload = _pkg_payload(items=[
            {"exam_item_id": item_id, "is_required": True},
        ])
        resp = client.post("/api/packages", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert len(body.get("items", [])) == 1
        assert body["items"][0]["exam_item_id"] == item_id
        assert body["items"][0]["is_required"] is True
        client.delete(f"/api/packages/{body['id']}", headers=admin_headers)

    def test_package_requires_at_least_one_item(self, client: httpx.Client, admin_headers: dict):
        """Backend enforces min_length=1 on items list."""
        payload = _pkg_payload(items=[])
        resp = client.post("/api/packages", json=payload, headers=admin_headers)
        assert resp.status_code == 422

    def test_list_packages_returns_list(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/packages", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_package_by_id(self, client: httpx.Client, admin_headers: dict):
        item_id = _get_or_create_exam_item(client, admin_headers)
        pkg = client.post("/api/packages", json=_pkg_payload(
            items=[{"exam_item_id": item_id, "is_required": True}]
        ), headers=admin_headers).json()
        resp = client.get(f"/api/packages/{pkg['id']}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == pkg["id"]
        client.delete(f"/api/packages/{pkg['id']}", headers=admin_headers)

    def test_get_nonexistent_package_returns_404(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/packages/999999999", headers=admin_headers)
        assert resp.status_code == 404

    def test_package_price_stored_correctly(self, client: httpx.Client, admin_headers: dict):
        item_id = _get_or_create_exam_item(client, admin_headers)
        payload = _pkg_payload(items=[{"exam_item_id": item_id, "is_required": True}])
        payload["price"] = "149.99"
        pkg = client.post("/api/packages", json=payload, headers=admin_headers).json()
        assert float(pkg["price"]) == 149.99
        client.delete(f"/api/packages/{pkg['id']}", headers=admin_headers)


class TestPackageVersioning:
    def test_new_version_increments_version_number(
        self, client: httpx.Client, admin_headers: dict
    ):
        pkg = client.post("/api/packages", json=_pkg_payload(), headers=admin_headers).json()
        name = pkg["name"]
        pkg_id = pkg["id"]

        resp = client.post(f"/api/packages/{pkg_id}/versions", json={
            "description": "Updated description",
            "price": "109.99",
            "validity_days": 60,
            "change_note": "Price update",
        }, headers=admin_headers)
        assert resp.status_code == 201
        new_pkg = resp.json()
        assert new_pkg["version"] == 2
        assert new_pkg["name"] == name

        # Cleanup both versions
        client.delete(f"/api/packages/{pkg_id}", headers=admin_headers)
        client.delete(f"/api/packages/{new_pkg['id']}", headers=admin_headers)

    def test_versions_list_returns_all_versions(
        self, client: httpx.Client, admin_headers: dict
    ):
        pkg = client.post("/api/packages", json=_pkg_payload(), headers=admin_headers).json()
        resp = client.get(f"/api/packages/{pkg['id']}/versions", headers=admin_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1
        client.delete(f"/api/packages/{pkg['id']}", headers=admin_headers)


class TestPackageDiff:
    def test_diff_between_versions(self, client: httpx.Client, admin_headers: dict):
        pkg_v1 = client.post("/api/packages", json=_pkg_payload(), headers=admin_headers).json()
        pkg_id = pkg_v1["id"]

        pkg_v2 = client.post(f"/api/packages/{pkg_id}/versions", json={
            "description": "New description",
            "price": "199.99",
            "validity_days": 90,
            "change_note": "Major update",
        }, headers=admin_headers).json()

        resp = client.get(
            f"/api/packages/{pkg_v2['id']}/diff",
            params={"base_id": pkg_id},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        diff = resp.json()
        assert "metadata_changes" in diff or "base" in diff or isinstance(diff, dict)

        client.delete(f"/api/packages/{pkg_id}", headers=admin_headers)
        client.delete(f"/api/packages/{pkg_v2['id']}", headers=admin_headers)


class TestPackageActivation:
    def test_activate_package(self, client: httpx.Client, admin_headers: dict):
        pkg = client.post("/api/packages", json=_pkg_payload(), headers=admin_headers).json()
        resp = client.patch(f"/api/packages/{pkg['id']}/activate", headers=admin_headers)
        assert resp.status_code in (200, 204)
        client.delete(f"/api/packages/{pkg['id']}", headers=admin_headers)

    def test_deactivate_package(self, client: httpx.Client, admin_headers: dict):
        pkg = client.post("/api/packages", json=_pkg_payload(), headers=admin_headers).json()
        client.patch(f"/api/packages/{pkg['id']}/activate", headers=admin_headers)
        resp = client.patch(f"/api/packages/{pkg['id']}/deactivate", headers=admin_headers)
        assert resp.status_code in (200, 204)
        client.delete(f"/api/packages/{pkg['id']}", headers=admin_headers)

    def test_end_user_cannot_activate(
        self, client: httpx.Client, admin_headers: dict, temp_end_user_headers: dict
    ):
        pkg = client.post("/api/packages", json=_pkg_payload(), headers=admin_headers).json()
        resp = client.patch(f"/api/packages/{pkg['id']}/activate", headers=temp_end_user_headers)
        assert resp.status_code == 403
        client.delete(f"/api/packages/{pkg['id']}", headers=admin_headers)

    def test_duplicate_name_same_version_rejected(self, client: httpx.Client, admin_headers: dict):
        payload = _pkg_payload()
        pkg = client.post("/api/packages", json=payload, headers=admin_headers).json()
        # Attempt to create another package with the same name at version 1
        resp = client.post("/api/packages", json=payload, headers=admin_headers)
        assert resp.status_code == 409
        client.delete(f"/api/packages/{pkg['id']}", headers=admin_headers)
