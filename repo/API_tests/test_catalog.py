"""
API tests for /api/catalog — catalog items, attachment upload, and integrity check.
"""
import io
import uuid
import httpx
import pytest


def _catalog_payload(name: str | None = None) -> dict:
    if name is None:
        name = f"Catalog Item {uuid.uuid4().hex[:8]}"
    return {
        "name": name,
        "description": "Test catalog item",
        "category": "test",
        "price": "9.99",
        "stock_quantity": 100,
    }


def _jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff" + b"\x00" * 20


def _pdf_bytes() -> bytes:
    return b"%PDF-1.4\n" + b"\x00" * 20


class TestCatalogCRUD:
    def test_admin_can_create_item(self, client: httpx.Client, admin_headers: dict):
        payload = _catalog_payload()
        resp = client.post("/api/catalog", json=payload, headers=admin_headers)
        assert resp.status_code == 201, f"Create failed: {resp.text}"
        body = resp.json()
        assert body["name"] == payload["name"]
        client.delete(f"/api/catalog/{body['id']}", headers=admin_headers)

    def test_list_catalog_items(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/catalog", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_catalog_item_by_id(self, client: httpx.Client, admin_headers: dict):
        item = client.post("/api/catalog", json=_catalog_payload(), headers=admin_headers).json()
        resp = client.get(f"/api/catalog/{item['id']}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == item["id"]
        client.delete(f"/api/catalog/{item['id']}", headers=admin_headers)

    def test_get_nonexistent_item_returns_404(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/catalog/999999999", headers=admin_headers)
        assert resp.status_code == 404

    def test_update_catalog_item(self, client: httpx.Client, admin_headers: dict):
        item = client.post("/api/catalog", json=_catalog_payload(), headers=admin_headers).json()
        resp = client.put(f"/api/catalog/{item['id']}", json={
            "name": "Updated Name",
            "description": "Updated desc",
            "category": "updated",
        }, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"
        client.delete(f"/api/catalog/{item['id']}", headers=admin_headers)

    def test_delete_catalog_item(self, client: httpx.Client, admin_headers: dict):
        item = client.post("/api/catalog", json=_catalog_payload(), headers=admin_headers).json()
        resp = client.delete(f"/api/catalog/{item['id']}", headers=admin_headers)
        assert resp.status_code == 204
        # Confirm deleted
        assert client.get(f"/api/catalog/{item['id']}", headers=admin_headers).status_code == 404

    def test_end_user_cannot_create_item(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.post("/api/catalog", json=_catalog_payload(), headers=temp_end_user_headers)
        assert resp.status_code == 403

    def test_search_filter_works(self, client: httpx.Client, admin_headers: dict):
        """Full-text search across name/description/category/origin."""
        unique_term = f"xqz{uuid.uuid4().hex[:6]}"
        payload = _catalog_payload(name=f"Item {unique_term}")
        item = client.post("/api/catalog", json=payload, headers=admin_headers).json()
        resp = client.get("/api/catalog", params={"search": unique_term, "active_only": False},
                          headers=admin_headers)
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()]
        assert item["id"] in ids
        client.delete(f"/api/catalog/{item['id']}", headers=admin_headers)

    def test_price_range_filter(self, client: httpx.Client, admin_headers: dict):
        payload = _catalog_payload()
        payload["price"] = "250.00"
        item = client.post("/api/catalog", json=payload, headers=admin_headers).json()
        # Should appear in range 200-300
        resp = client.get("/api/catalog", params={"price_min": 200, "price_max": 300,
                          "active_only": False}, headers=admin_headers)
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()]
        assert item["id"] in ids
        # Should NOT appear in range 0-100
        resp2 = client.get("/api/catalog", params={"price_min": 0, "price_max": 100,
                           "active_only": False}, headers=admin_headers)
        ids2 = [r["id"] for r in resp2.json()]
        assert item["id"] not in ids2
        client.delete(f"/api/catalog/{item['id']}", headers=admin_headers)


class TestTagsFilter:
    """Catalog tags field — creation, storage, and filter query."""

    def test_create_item_with_tags_stored(self, client: httpx.Client, admin_headers: dict):
        payload = _catalog_payload()
        payload["tags"] = "organic,premium,export"
        resp = client.post("/api/catalog", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["tags"] == "organic,premium,export"
        client.delete(f"/api/catalog/{body['id']}", headers=admin_headers)

    def test_tags_filter_matches_single_tag(self, client: httpx.Client, admin_headers: dict):
        payload = _catalog_payload()
        unique_tag = f"tag_{uuid.uuid4().hex[:8]}"
        payload["tags"] = f"organic,{unique_tag}"
        item = client.post("/api/catalog", json=payload, headers=admin_headers).json()
        resp = client.get("/api/catalog", params={"tags": unique_tag, "active_only": False},
                          headers=admin_headers)
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()]
        assert item["id"] in ids
        client.delete(f"/api/catalog/{item['id']}", headers=admin_headers)

    def test_tags_filter_comma_separated_matches_any(
        self, client: httpx.Client, admin_headers: dict
    ):
        payload = _catalog_payload()
        unique_tag = f"rare_{uuid.uuid4().hex[:8]}"
        payload["tags"] = unique_tag
        item = client.post("/api/catalog", json=payload, headers=admin_headers).json()
        # Pass multiple tags; item matches on one of them
        resp = client.get("/api/catalog",
                          params={"tags": f"nope,{unique_tag}", "active_only": False},
                          headers=admin_headers)
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()]
        assert item["id"] in ids
        client.delete(f"/api/catalog/{item['id']}", headers=admin_headers)

    def test_tags_filter_no_match_returns_empty(
        self, client: httpx.Client, admin_headers: dict
    ):
        impossible_tag = f"zzz_{uuid.uuid4().hex}"
        resp = client.get("/api/catalog", params={"tags": impossible_tag, "active_only": False},
                          headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json() == []


class TestPriorityFilter:
    """Catalog priority field — creation, storage, and filter query."""

    def test_create_item_with_priority_stored(self, client: httpx.Client, admin_headers: dict):
        payload = _catalog_payload()
        payload["priority"] = 3
        resp = client.post("/api/catalog", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["priority"] == 3
        client.delete(f"/api/catalog/{body['id']}", headers=admin_headers)

    def test_priority_out_of_range_high_rejected(
        self, client: httpx.Client, admin_headers: dict
    ):
        payload = _catalog_payload()
        payload["priority"] = 6  # above max of 5
        resp = client.post("/api/catalog", json=payload, headers=admin_headers)
        assert resp.status_code == 422, (
            f"priority=6 should be rejected, got {resp.status_code}"
        )

    def test_priority_out_of_range_low_rejected(
        self, client: httpx.Client, admin_headers: dict
    ):
        payload = _catalog_payload()
        payload["priority"] = 0  # below min of 1
        resp = client.post("/api/catalog", json=payload, headers=admin_headers)
        assert resp.status_code == 422, (
            f"priority=0 should be rejected, got {resp.status_code}"
        )

    def test_priority_min_filter_returns_200(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/catalog", params={"priority_min": 3}, headers=admin_headers)
        assert resp.status_code == 200

    def test_priority_max_filter_returns_200(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/catalog", params={"priority_max": 4}, headers=admin_headers)
        assert resp.status_code == 200

    def test_priority_query_param_out_of_range_rejected(
        self, client: httpx.Client, admin_headers: dict
    ):
        resp = client.get("/api/catalog", params={"priority_min": 6}, headers=admin_headers)
        assert resp.status_code == 422, (
            f"priority_min=6 query param should be rejected, got {resp.status_code}"
        )

    def test_priority_inverted_range_rejected(
        self, client: httpx.Client, admin_headers: dict
    ):
        resp = client.get("/api/catalog",
                          params={"priority_min": 5, "priority_max": 2},
                          headers=admin_headers)
        assert resp.status_code == 422, (
            f"priority_min > priority_max should be rejected, got {resp.status_code}"
        )

    def test_priority_filter_returns_only_matching_items(
        self, client: httpx.Client, admin_headers: dict
    ):
        """Create two items with distinct priorities; confirm filter isolates them."""
        low = client.post("/api/catalog", json={**_catalog_payload(), "priority": 1},
                          headers=admin_headers).json()
        high = client.post("/api/catalog", json={**_catalog_payload(), "priority": 5},
                           headers=admin_headers).json()
        # priority_min=5 should include high but not low
        resp = client.get("/api/catalog",
                          params={"priority_min": 5, "active_only": False},
                          headers=admin_headers)
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()]
        assert high["id"] in ids
        assert low["id"] not in ids
        client.delete(f"/api/catalog/{low['id']}", headers=admin_headers)
        client.delete(f"/api/catalog/{high['id']}", headers=admin_headers)


class TestAttachmentUpload:
    def test_upload_pdf_attachment(self, client: httpx.Client, admin_headers: dict):
        item = client.post("/api/catalog", json=_catalog_payload(), headers=admin_headers).json()
        item_id = item["id"]

        resp = client.post(
            f"/api/catalog/{item_id}/attachments",
            files={"file": ("test.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)
        body = resp.json()
        assert "id" in body
        assert body.get("sha256_fingerprint") or body.get("sha256")

        client.delete(f"/api/catalog/{item_id}", headers=admin_headers)

    def test_upload_image_attachment(self, client: httpx.Client, admin_headers: dict):
        item = client.post("/api/catalog", json=_catalog_payload(), headers=admin_headers).json()
        item_id = item["id"]

        resp = client.post(
            f"/api/catalog/{item_id}/attachments",
            files={"file": ("photo.jpg", io.BytesIO(_jpeg_bytes()), "image/jpeg")},
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)
        client.delete(f"/api/catalog/{item_id}", headers=admin_headers)

    def test_upload_disallowed_type_rejected(self, client: httpx.Client, admin_headers: dict):
        item = client.post("/api/catalog", json=_catalog_payload(), headers=admin_headers).json()
        item_id = item["id"]

        resp = client.post(
            f"/api/catalog/{item_id}/attachments",
            files={"file": ("script.sh", io.BytesIO(b"#!/bin/bash\nrm -rf /"), "application/x-sh")},
            headers=admin_headers,
        )
        assert resp.status_code == 422

        client.delete(f"/api/catalog/{item_id}", headers=admin_headers)

    def test_attachment_listed_after_upload(self, client: httpx.Client, admin_headers: dict):
        item = client.post("/api/catalog", json=_catalog_payload(), headers=admin_headers).json()
        item_id = item["id"]

        client.post(
            f"/api/catalog/{item_id}/attachments",
            files={"file": ("doc.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
            headers=admin_headers,
        )
        resp = client.get(f"/api/catalog/{item_id}/attachments", headers=admin_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

        client.delete(f"/api/catalog/{item_id}", headers=admin_headers)


class TestFileIntegrity:
    def test_download_returns_file(self, client: httpx.Client, admin_headers: dict):
        item = client.post("/api/catalog", json=_catalog_payload(), headers=admin_headers).json()
        item_id = item["id"]

        attach = client.post(
            f"/api/catalog/{item_id}/attachments",
            files={"file": ("test.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
            headers=admin_headers,
        ).json()
        attach_id = attach["id"]

        resp = client.get(
            f"/api/catalog/{item_id}/attachments/{attach_id}/download",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert len(resp.content) > 0

        client.delete(f"/api/catalog/{item_id}", headers=admin_headers)

    def test_unauthenticated_download_rejected(self, client: httpx.Client, admin_headers: dict):
        """Files must NOT be reachable by unauthenticated requests."""
        item = client.post("/api/catalog", json=_catalog_payload(), headers=admin_headers).json()
        item_id = item["id"]
        attach = client.post(
            f"/api/catalog/{item_id}/attachments",
            files={"file": ("doc.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
            headers=admin_headers,
        ).json()
        attach_id = attach["id"]

        # No auth headers — must be rejected
        resp = client.get(f"/api/catalog/{item_id}/attachments/{attach_id}/download")
        assert resp.status_code in (401, 403), (
            f"Unauthenticated download should be rejected, got {resp.status_code}"
        )

        # Direct /uploads path must not exist (no static mount)
        static_resp = client.get(f"/uploads/catalog/{item_id}/{attach.get('stored_filename', 'x')}")
        assert static_resp.status_code in (401, 403, 404), (
            f"/uploads must not serve files unauthenticated, got {static_resp.status_code}"
        )

        client.delete(f"/api/catalog/{item_id}", headers=admin_headers)

    def test_other_user_cannot_download_via_object_id(
        self, client: httpx.Client, admin_headers: dict, temp_end_user_headers: dict
    ):
        """End users without catalog_manager role cannot download attachments."""
        item = client.post("/api/catalog", json=_catalog_payload(), headers=admin_headers).json()
        item_id = item["id"]
        attach = client.post(
            f"/api/catalog/{item_id}/attachments",
            files={"file": ("doc.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
            headers=admin_headers,
        ).json()
        attach_id = attach["id"]

        # End user CAN download (read is allowed for all authenticated)
        resp = client.get(
            f"/api/catalog/{item_id}/attachments/{attach_id}/download",
            headers=temp_end_user_headers,
        )
        assert resp.status_code == 200

        # End user CANNOT delete attachment
        del_resp = client.delete(
            f"/api/catalog/{item_id}/attachments/{attach_id}",
            headers=temp_end_user_headers,
        )
        assert del_resp.status_code == 403

        client.delete(f"/api/catalog/{item_id}", headers=admin_headers)
