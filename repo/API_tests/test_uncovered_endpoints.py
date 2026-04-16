"""
Explicit no-mock HTTP tests for previously-identified uncovered endpoints:

  - PUT    /api/admin/api-keys/{key_id}
  - POST   /api/packages/{package_id}/items
  - DELETE /api/packages/{package_id}/items/{exam_item_id}

Each test:
  - runs against the real containerized backend via httpx
  - authenticates with real tokens, creates real entities
  - asserts both status and response body semantics
  - covers at least one failure/permission path
  - is idempotent and self-cleaning
"""
import uuid

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers — create the entities we need via real API calls
# ---------------------------------------------------------------------------

def _create_exam_item(client: httpx.Client, headers: dict) -> dict:
    uid = uuid.uuid4().hex[:6].upper()
    resp = client.post(
        "/api/exam-items",
        json={
            "code": f"EI-{uid}",
            "name": f"Exam Item {uid}",
            "unit": "mg/dL",
            "applicable_sex": "all",
        },
        headers=headers,
    )
    assert resp.status_code == 201, f"exam item creation failed: {resp.text}"
    return resp.json()


def _create_package_with_item(client: httpx.Client, headers: dict) -> tuple[dict, dict]:
    """Create a package with a single exam item. Returns (package, exam_item)."""
    ei = _create_exam_item(client, headers)
    resp = client.post(
        "/api/packages",
        json={
            "name": f"Package-{uuid.uuid4().hex[:6]}",
            "description": "Coverage test package",
            "price": "99.99",
            "items": [{"exam_item_id": ei["id"], "is_required": True}],
        },
        headers=headers,
    )
    assert resp.status_code == 201, f"package creation failed: {resp.text}"
    return resp.json(), ei


def _delete_package_chain(client: httpx.Client, headers: dict, pkg: dict, exam_item: dict) -> None:
    # Delete any derived versions created during tests, then the original.
    versions = client.get(
        f"/api/packages/{pkg['id']}/versions", headers=headers,
    ).json()
    for v in versions:
        client.delete(f"/api/packages/{v['id']}", headers=headers)
    client.delete(f"/api/packages/{pkg['id']}", headers=headers)
    client.delete(f"/api/exam-items/{exam_item['id']}", headers=headers)


# ===========================================================================
# PUT /api/admin/api-keys/{key_id}
# ===========================================================================

class TestPutApiKey:
    """Admin can update an API key's metadata via PUT /api/admin/api-keys/{id}."""

    def test_admin_can_update_api_key_label_and_rate_limit(
        self,
        client: httpx.Client,
        admin_headers: dict,
    ):
        # Arrange — create a real API key
        create = client.post(
            "/api/admin/api-keys",
            json={
                "label": f"original-{uuid.uuid4().hex[:6]}",
                "system_name": "upstream-sync",
                "rate_limit_per_minute": 60,
            },
            headers=admin_headers,
        )
        assert create.status_code == 201, create.text
        key = create.json()
        key_id = key["id"]
        original_label = key["label"]

        try:
            # Act — PUT updates label + rate_limit_per_minute
            new_label = f"renamed-{uuid.uuid4().hex[:6]}"
            resp = client.put(
                f"/api/admin/api-keys/{key_id}",
                json={
                    "label": new_label,
                    "rate_limit_per_minute": 120,
                },
                headers=admin_headers,
            )

            # Assert — status + response body reflect the update
            assert resp.status_code == 200, f"PUT failed: {resp.text}"
            body = resp.json()
            assert body["id"] == key_id
            assert body["label"] == new_label
            assert body["label"] != original_label
            assert body["rate_limit_per_minute"] == 120
            # Sensitive fields must never leak on update
            assert "raw_key" not in body
            assert "key_hash" not in body

            # Read-back via GET confirms persistence
            got = client.get(f"/api/admin/api-keys/{key_id}", headers=admin_headers)
            assert got.status_code == 200
            assert got.json()["label"] == new_label
            assert got.json()["rate_limit_per_minute"] == 120
        finally:
            client.delete(f"/api/admin/api-keys/{key_id}", headers=admin_headers)

    def test_put_api_key_nonexistent_returns_404(
        self, client: httpx.Client, admin_headers: dict,
    ):
        resp = client.put(
            "/api/admin/api-keys/999999999",
            json={"label": "ghost"},
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_put_api_key_empty_body_rejected(
        self, client: httpx.Client, admin_headers: dict,
    ):
        """Empty update body must be rejected (422) — no-op updates not allowed."""
        create = client.post(
            "/api/admin/api-keys",
            json={"label": f"empty-{uuid.uuid4().hex[:6]}", "system_name": "x"},
            headers=admin_headers,
        ).json()
        try:
            resp = client.put(
                f"/api/admin/api-keys/{create['id']}",
                json={},
                headers=admin_headers,
            )
            assert resp.status_code == 422
        finally:
            client.delete(f"/api/admin/api-keys/{create['id']}", headers=admin_headers)

    def test_end_user_cannot_update_api_key(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user_headers: dict,
    ):
        """RBAC: only admin can update API keys."""
        create = client.post(
            "/api/admin/api-keys",
            json={"label": f"rbac-{uuid.uuid4().hex[:6]}", "system_name": "x"},
            headers=admin_headers,
        ).json()
        try:
            resp = client.put(
                f"/api/admin/api-keys/{create['id']}",
                json={"label": "hacked"},
                headers=temp_end_user_headers,
            )
            assert resp.status_code == 403
            # Verify the label was NOT changed
            got = client.get(
                f"/api/admin/api-keys/{create['id']}", headers=admin_headers,
            )
            assert got.json()["label"] == create["label"]
        finally:
            client.delete(f"/api/admin/api-keys/{create['id']}", headers=admin_headers)


# ===========================================================================
# POST /api/packages/{package_id}/items
# ===========================================================================

class TestAddItemToPackage:
    """Adding an item creates a NEW package version that contains the addition."""

    def test_add_item_creates_new_version_with_appended_item(
        self, client: httpx.Client, admin_headers: dict,
    ):
        pkg, ei1 = _create_package_with_item(client, admin_headers)
        ei2 = _create_exam_item(client, admin_headers)
        try:
            # Act — POST adds ei2 to the package, creating version 2
            resp = client.post(
                f"/api/packages/{pkg['id']}/items",
                json={"exam_item_id": ei2["id"], "is_required": True},
                headers=admin_headers,
            )

            # Assert — a new package version exists with BOTH items
            assert resp.status_code == 201, f"add-item failed: {resp.text}"
            new_pkg = resp.json()
            assert new_pkg["version"] == pkg["version"] + 1, (
                f"Expected version {pkg['version'] + 1}, got {new_pkg['version']}"
            )
            assert new_pkg["name"] == pkg["name"]
            assert new_pkg["is_active"] is False, (
                "New version must start inactive per packaging contract"
            )
            item_ids = [it["exam_item_id"] for it in new_pkg["items"]]
            assert ei1["id"] in item_ids
            assert ei2["id"] in item_ids
            assert len(new_pkg["items"]) == 2
        finally:
            _delete_package_chain(client, admin_headers, pkg, ei1)
            client.delete(f"/api/exam-items/{ei2['id']}", headers=admin_headers)

    def test_add_duplicate_item_returns_409(
        self, client: httpx.Client, admin_headers: dict,
    ):
        pkg, ei = _create_package_with_item(client, admin_headers)
        try:
            resp = client.post(
                f"/api/packages/{pkg['id']}/items",
                json={"exam_item_id": ei["id"], "is_required": True},
                headers=admin_headers,
            )
            assert resp.status_code == 409
            detail = resp.json().get("detail", "").lower()
            assert "already" in detail or "exists" in detail
        finally:
            _delete_package_chain(client, admin_headers, pkg, ei)

    def test_add_item_nonexistent_package_returns_404(
        self, client: httpx.Client, admin_headers: dict,
    ):
        ei = _create_exam_item(client, admin_headers)
        try:
            resp = client.post(
                "/api/packages/999999999/items",
                json={"exam_item_id": ei["id"], "is_required": True},
                headers=admin_headers,
            )
            assert resp.status_code == 404
        finally:
            client.delete(f"/api/exam-items/{ei['id']}", headers=admin_headers)

    def test_end_user_cannot_add_item_to_package(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user_headers: dict,
    ):
        pkg, ei = _create_package_with_item(client, admin_headers)
        ei2 = _create_exam_item(client, admin_headers)
        try:
            resp = client.post(
                f"/api/packages/{pkg['id']}/items",
                json={"exam_item_id": ei2["id"], "is_required": True},
                headers=temp_end_user_headers,
            )
            assert resp.status_code == 403
        finally:
            _delete_package_chain(client, admin_headers, pkg, ei)
            client.delete(f"/api/exam-items/{ei2['id']}", headers=admin_headers)


# ===========================================================================
# DELETE /api/packages/{package_id}/items/{exam_item_id}
# ===========================================================================

class TestRemoveItemFromPackage:
    """Removing an item creates a NEW package version missing that item."""

    def test_remove_item_creates_new_version_without_that_item(
        self, client: httpx.Client, admin_headers: dict,
    ):
        # Arrange — package with two items
        ei1 = _create_exam_item(client, admin_headers)
        ei2 = _create_exam_item(client, admin_headers)
        pkg = client.post(
            "/api/packages",
            json={
                "name": f"Package-{uuid.uuid4().hex[:6]}",
                "description": "Removal test",
                "price": "49.99",
                "items": [
                    {"exam_item_id": ei1["id"], "is_required": True},
                    {"exam_item_id": ei2["id"], "is_required": True},
                ],
            },
            headers=admin_headers,
        ).json()

        try:
            # Act — remove ei1
            resp = client.delete(
                f"/api/packages/{pkg['id']}/items/{ei1['id']}",
                headers=admin_headers,
            )

            # Assert — new version has only ei2
            assert resp.status_code == 200, f"remove-item failed: {resp.text}"
            new_pkg = resp.json()
            assert new_pkg["version"] == pkg["version"] + 1
            item_ids = [it["exam_item_id"] for it in new_pkg["items"]]
            assert ei1["id"] not in item_ids
            assert ei2["id"] in item_ids
            assert len(new_pkg["items"]) == 1
            assert new_pkg["is_active"] is False
        finally:
            _delete_package_chain(client, admin_headers, pkg, ei1)
            client.delete(f"/api/exam-items/{ei2['id']}", headers=admin_headers)

    def test_remove_nonexistent_item_returns_404(
        self, client: httpx.Client, admin_headers: dict,
    ):
        pkg, ei = _create_package_with_item(client, admin_headers)
        try:
            resp = client.delete(
                f"/api/packages/{pkg['id']}/items/999999",
                headers=admin_headers,
            )
            assert resp.status_code == 404
        finally:
            _delete_package_chain(client, admin_headers, pkg, ei)

    def test_remove_last_item_rejected(
        self, client: httpx.Client, admin_headers: dict,
    ):
        """Business rule: a package must retain at least one item."""
        pkg, ei = _create_package_with_item(client, admin_headers)
        try:
            resp = client.delete(
                f"/api/packages/{pkg['id']}/items/{ei['id']}",
                headers=admin_headers,
            )
            assert resp.status_code == 422
            detail = resp.json().get("detail", "").lower()
            assert "last item" in detail or "at least one" in detail
        finally:
            _delete_package_chain(client, admin_headers, pkg, ei)

    def test_end_user_cannot_remove_item_from_package(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user_headers: dict,
    ):
        pkg, ei = _create_package_with_item(client, admin_headers)
        ei2 = _create_exam_item(client, admin_headers)
        # Add a second item so we're not constrained by the last-item rule
        add_resp = client.post(
            f"/api/packages/{pkg['id']}/items",
            json={"exam_item_id": ei2["id"], "is_required": True},
            headers=admin_headers,
        )
        assert add_resp.status_code == 201, add_resp.text
        new_pkg = add_resp.json()
        try:
            resp = client.delete(
                f"/api/packages/{new_pkg['id']}/items/{ei2['id']}",
                headers=temp_end_user_headers,
            )
            assert resp.status_code == 403
        finally:
            _delete_package_chain(client, admin_headers, pkg, ei)
            client.delete(f"/api/exam-items/{ei2['id']}", headers=admin_headers)
